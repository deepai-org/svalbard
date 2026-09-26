"""Whole-chip architecture screening without analog ODE integration.

Protocol names exist only in the external scenario runner. Quality equations are
conditional budgets, not modem simulation or standards-compliance verdicts.
"""
from dataclasses import dataclass, asdict, replace
from collections import deque
from bisect import bisect_right
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time

P = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(P / 'verification'))
sys.path.insert(0, str(P / 'system_model/connected'))
import numpy as np
from protocol_signals import fixture, decisions, gfsk, lora, he20, TrainedBlockEqualizer, repeated_training_frequency
from scipy.signal import lfilter, butter, residue
from fractions import Fraction
from stream_codec import slots, metadata as stream_metadata
from block_receiver_model import BlockFIFO
from lane_group import forwarded_pll_acquisition
from protocol_pad import SharedWiredPad, usb_nrzi, usb_decode, usb_framed_turnaround
from resource_configuration import decode_resource_word, encode_resource_word, validate_wire_timing, validate_rf_settings
from sampled_pll import SampledPLL
from autonomous_pll import AutonomousPLL
from reference_sample_clock import ReferenceSampleClock


@dataclass(frozen=True)
class Assumptions:
    startup_s: float = 20e-6
    converter_enob: float = 9.
    sample_jitter_s: float = 2e-12
    relative_lo_phase_rms_rad: float = .03
    frontend_evm_rms: float = .04
    converter_backoff_db: float = 12.
    wire_random_jitter_s: float = 5e-12
    wire_deterministic_jitter_ui: float = .10
    wire_channel_closure_ui: float = .20
    host_clock_scale: float = 1.
    source_clock_scale: float = 1.
    h2d_clock_scale: float = 1.
    d2h_clock_scale: float = 1.
    supply_v: float = 3.3
    host_output_cap_f: float = 10e-12
    host_data_rising_probability: float = .25
    core_bias_a: float = .020
    pll_bias_a: float = .008
    rf_bias_a: float = .012
    wire_bias_a: float = .005
    host_segment_bias_a: float = .002
    rf_output_power_w: float = .001
    rf_efficiency: float = .35
    feed_resistance_ohm: float = 2.
    return_resistance_ohm: float = .1
    minimum_supply_v: float = 2.5


class SupplyRangeError(ValueError):
    """A sampled supply event is outside the declared model range."""


class LiveRFTransportFailure(ValueError):
    def __init__(self,report):
        super().__init__(report['flow']['fault'] or 'incomplete_delivery')
        self.report=report


class SharedRail:
    """Series R/L feed, shunt C and LO pulling; no regulator or validated package."""
    def __init__(self,*,time=0.,resistance_ohm=2.,capacitance_f=1e-9,
                 host_coupling=.1,host_cap_f=10e-12,converter_charge_c=20e-12,
                 lo_hz_per_v=10e6,nominal_v=3.3,rf_gain_fraction=1.,inductance_h=0.,
                 full_host_activity=False,input_transition_charge_c=0.,host_clock_phase='auto',block_write_cap_f=0.,block_read_cap_f=0.,block_clock_coupling=1.,bias_current_a=0.):
        if not math.isfinite(bias_current_a) or bias_current_a<0:raise ValueError('Finite nonnegative rail bias required')
        self.bias=bias_current_a;self.bias_charge=0.
        values=(resistance_ohm,capacitance_f,host_coupling,host_cap_f,converter_charge_c,lo_hz_per_v,nominal_v,rf_gain_fraction,inductance_h)
        if not all(math.isfinite(v) and v>=0 for v in values) or min(resistance_ohm,capacitance_f,nominal_v)<=0 or host_coupling>1:
            raise ValueError('Finite passive shared-rail parameters required')
        if host_clock_phase=='auto':host_clock_phase=0 if full_host_activity else None
        if host_clock_phase is not None and (type(host_clock_phase) is not int or host_clock_phase not in (0,1)):
            raise ValueError('Clock phase must be zero/one or averaged None')
        if not all(math.isfinite(v) and v>=0 for v in (block_write_cap_f,block_read_cap_f,block_clock_coupling)) or block_clock_coupling>1:
            raise ValueError('Finite block clock capacitances and coupling in [0,1] required')
        self.block_caps=(block_write_cap_f,block_read_cap_f);self.block_coupling=block_clock_coupling
        self.block_edges=[0,0];self.block_charge=0.
        self.host_clock_phase=host_clock_phase;self.host_clock_rises=0.
        self.r=resistance_ohm;self.c=capacitance_f;self.l=inductance_h;self.current=0.;self.host_coupling=host_coupling
        self.host_cap=host_cap_f;self.converter_charge=converter_charge_c
        self.lo_sensitivity=lo_hz_per_v;self.nominal=nominal_v;self.rf_gain_fraction=rf_gain_fraction
        self.time=time;self.droop=0.;self.phase=0.;self.charge=0.;self.recovered=0.
        self.pulse_clock=None;self.pulse_clock_intervals=0
        self.minimum_v=nominal_v;self.maximum_v=nominal_v;self.last_word=0;self.host_events=0;self.converter_events=0
        if type(full_host_activity) is not bool or not math.isfinite(input_transition_charge_c) or input_transition_charge_c<0:
            raise ValueError('Boolean host activity selector and nonnegative input charge required')
        if input_transition_charge_c and not full_host_activity:
            raise ValueError('Input switching charge requires complete host activity')
        self.full_host_activity=full_host_activity;self.input_charge=input_transition_charge_c
        self.last_input_word=0;self.input_events=0;self.input_transitions=0;self.input_total_charge=0.

    @property
    def voltage(self):return self.nominal-self.droop

    def _transition(self,dt,droop,current):
        droop-=self.r*self.bias;current-=self.bias
        alpha=self.r/(2*self.l);omega2=1/(self.l*self.c);delta=omega2-alpha*alpha
        if abs(delta)<=1e-12*omega2:
            ec=math.exp(-alpha*dt);es=ec*dt
        elif delta>0:
            omega=math.sqrt(delta);decay=math.exp(-alpha*dt)
            ec=decay*math.cos(omega*dt);es=decay*math.sin(omega*dt)/omega
        else:
            root=math.sqrt(-delta)
            slow=math.exp(-omega2/(alpha+root)*dt);fast=math.exp((-alpha-root)*dt)
            ec=(slow+fast)/2;es=(slow-fast)/(2*root)
        return (self.r*self.bias+ec*droop+es*(alpha*droop-current/self.c),
                self.bias+ec*current+es*(droop/self.l-alpha*current))

    def droop_at(self,dt):
        if self.l:return self._transition(dt,self.droop,self.current)[0]
        steady=self.r*self.bias
        return steady+(self.droop-steady)*math.exp(-dt/(self.r*self.c))

    def droop_integral(self,begin,end):
        if self.l:
            a,ia=self._transition(begin,self.droop,self.current)
            b,ib=self._transition(end,self.droop,self.current)
            return self.l*(ib-ia)+self.r*(self.c*(a-b)+self.bias*(end-begin))
        tau=self.r*self.c;steady=self.r*self.bias
        residual=(self.droop-steady)*math.exp(-begin/tau)
        return steady*(end-begin)+residual*tau*(-math.expm1(-(end-begin)/tau))

    def droop_bound(self):
        return self.r*self.bias+math.sqrt((self.droop-self.r*self.bias)**2+
            self.l/self.c*(self.current-self.bias)**2)

    def attach_pulse_clock(self,clock):
        if self.pulse_clock is not None or not isinstance(clock,RailDrivenPulsePLL) or clock.time!=self.time:
            raise ValueError('Attach one pulse PLL at the common rail epoch')
        self.pulse_clock=clock

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic rail time required')
        clock_failed=False
        if self.pulse_clock is not None and time>self.time:
            self.pulse_clock.bind_rail_interval(self,time)
            clock_failed=not self.pulse_clock.advance(time)
            time=self.pulse_clock.time;self.pulse_clock_intervals+=1
        dt=time-self.time
        if not self.l:
            tau=self.r*self.c;fraction=-math.expm1(-dt/tau)
            residual=self.droop-self.r*self.bias
            integral=self.r*self.bias*dt+residual*tau*fraction
            self.recovered+=self.c*residual*fraction+self.bias*dt
            self.droop=self.r*self.bias+residual*(1-fraction)
        else:
            before=self.droop;current=self.current
            after,new_current=self._transition(dt,before,current)
            # Interior extrema occur at feed-current zero; include both first
            # extrema in the underdamped case (later peaks decay).
            alpha=self.r/(2*self.l);omega2=1/(self.l*self.c);delta=omega2-alpha*alpha
            residual_current=current-self.bias
            slope=(before-self.r*self.bias)/self.l-alpha*residual_current;extrema=[]
            if abs(delta)<=1e-12*omega2:
                if slope:extrema=[-residual_current/slope]
            elif delta>0:
                omega=math.sqrt(delta)
                first=(math.atan2(-residual_current,slope/omega)%math.pi)/omega
                extrema=[first,first+math.pi/omega]
            else:
                root=math.sqrt(-delta);aa=(residual_current+slope/root)/2;bb=(residual_current-slope/root)/2
                if aa and -bb/aa>0:extrema=[math.log(-bb/aa)/(2*root)]
            peak=max(before,after);trough=min(before,after)
            for at in extrema:
                if 0<at<dt:
                    value=self._transition(at,before,current)[0]
                    peak=max(peak,value);trough=min(trough,value)
            self.minimum_v=min(self.minimum_v,self.nominal-peak)
            self.maximum_v=max(self.maximum_v,self.nominal-trough)
            recovered=self.c*(before-after)+self.bias*dt
            integral=self.l*(new_current-current)+self.r*recovered
            self.recovered+=recovered;self.droop=after;self.current=new_current
        self.bias_charge+=self.bias*dt;self.charge+=self.bias*dt
        self.minimum_v=min(self.minimum_v,self.voltage);self.maximum_v=max(self.maximum_v,self.voltage)
        self.phase-=2*math.pi*self.lo_sensitivity*integral
        self.time=time
        if clock_failed:raise ClockQualificationError('Shared-rail pulse PLL left compliance')

    def load(self,charge):
        self.charge+=charge;self.droop+=charge/self.c
        self.minimum_v=min(self.minimum_v,self.voltage)

    def host_word(self,word=None):
        # Optional DDR edges retain alternating phase across word callbacks.
        rises=.5 if self.host_clock_phase is None else float((self.host_events+self.host_clock_phase)%2==0)
        self.host_clock_rises+=rises
        if word is not None:
            rises+=(word&~self.last_word&1023).bit_count();self.last_word=word
        self.load(rises*self.host_cap*self.nominal*self.host_coupling);self.host_events+=1

    def converter(self):
        self.load(self.converter_charge);self.converter_events+=1

    def host_input(self,word):
        # Effective local receiver charge per transition, including one DDR
        # clock transition per word. External line charging belongs to the FPGA.
        if type(word) is not int or not 0<=word<1024:raise ValueError('Ten-bit input word required')
        transitions=(word^self.last_input_word).bit_count()+1
        charge=transitions*self.input_charge
        self.load(charge);self.last_input_word=word
        self.input_events+=1;self.input_transitions+=transitions;self.input_total_charge+=charge

    def block_clocks(self,write,read):
        if type(write) is not bool or type(read) is not bool:raise ValueError('Boolean clock edges required')
        charge=sum(c*int(edge) for c,edge in zip(self.block_caps,(write,read)))*self.nominal*self.block_coupling
        self.block_edges[0]+=int(write);self.block_edges[1]+=int(read)
        self.block_charge+=charge
        if charge:self.load(charge)

    def report(self):
        balance=self.charge-self.recovered-self.c*self.droop
        return dict(minimum_v=self.minimum_v,maximum_v=self.maximum_v,final_v=self.voltage,lo_phase_rad=self.phase,
            injected_charge_c=self.charge,recovered_charge_c=self.recovered,
            bias_current_a=self.bias,bias_charge_c=self.bias_charge,
            charge_balance_error_c=balance,host_events=self.host_events,converter_events=self.converter_events,
            resistance_ohm=self.r,capacitance_f=self.c,inductance_h=self.l,feed_current_a=self.current if self.l else self.droop/self.r,host_coupling=self.host_coupling,
            host_cap_f=self.host_cap,converter_charge_c=self.converter_charge,lo_hz_per_v=self.lo_sensitivity,rf_gain_fraction=self.rf_gain_fraction,
            full_host_activity=self.full_host_activity,host_clock_phase=self.host_clock_phase,host_clock_rises=self.host_clock_rises,input_transition_charge_c=self.input_charge,
            input_events=self.input_events,input_transitions=self.input_transitions,input_charge_c=self.input_total_charge,
            block_write_cap_f=self.block_caps[0],block_read_cap_f=self.block_caps[1],block_clock_coupling=self.block_coupling,
            block_write_edges=self.block_edges[0],block_read_edges=self.block_edges[1],block_clock_charge_c=self.block_charge)


class ReferencePresence:
    """External edge stimulus observed by an assumed independent monitor timer.

    This checks missing pulses, not PLL phase/frequency lock. Future stimulus
    never qualifies readiness; a pulse on the expiration tick wins the tie.
    """
    def __init__(self, edges, timeout_s=100e-9, monitor_tick_s=10e-9, required_edges=4):
        self.edges=tuple(edges)
        if (not all(math.isfinite(t) and t>=0 for t in self.edges)
                or any(b<=a for a,b in zip(self.edges,self.edges[1:]))
                or not all(math.isfinite(t) and t>0 for t in (timeout_s,monitor_tick_s))
                or type(required_edges) is not int or required_edges<1):
            raise ValueError('Ordered finite reference edges and positive monitor settings required')
        self.timeout=timeout_s;self.tick=monitor_tick_s;self.required=required_edges
        self.armed_at=0.

    def deadline(self,last):
        return self.armed_at+math.ceil((last+self.timeout-self.armed_at)/self.tick-1e-10)*self.tick

    def fault_between(self,begin,end):
        index=bisect_right(self.edges,begin)
        last=max(self.armed_at,self.edges[index-1] if index else self.armed_at)
        deadline=max(begin,self.deadline(last))
        while index<len(self.edges) and self.edges[index]<=end:
            edge=self.edges[index]
            if edge>deadline:return deadline
            deadline=self.deadline(edge);index+=1
        return deadline if deadline<=end else None

    def qualified(self,time):
        index=bisect_right(self.edges,time)
        recent=self.edges[max(0,index-self.required):index]
        return (len(recent)==self.required and recent[0]>=self.armed_at
                and time<self.deadline(recent[-1])
                and all(b<=self.deadline(a) for a,b in zip(recent,recent[1:])))


class ReferenceLossError(ValueError):
    pass


from shaped_fractional_pll import ThirdOrderFractionalPLL


class RailDrivenPulsePLL(ThirdOrderFractionalPLL):
    """Candidate actual-edge PLL consuming a bounded shared-rail event interval."""
    def __init__(self,*,require_acquisition=False,reference_events=(),**parameters):
        if type(require_acquisition) is not bool:raise ValueError('Boolean acquisition policy required')
        self.rail_segment=None
        self.phase_intervals=deque(maxlen=512)
        super().__init__(**parameters)
        from fractional_pulse_screen import CountedAcquisition
        self.acquisition=CountedAcquisition(self.rate,reference_hz=self.reference,
            window_edges=math.ceil(self.reference*500e-6)) if require_acquisition else None
        self.first_acquired=None
        self.reference_events=tuple(tuple(event) for event in reference_events)
        previous=-1.
        for event in self.reference_events:
            if (len(event)!=2 or not math.isfinite(event[0]) or event[0]<0
                    or event[0]<=previous or type(event[1]) is not bool):
                raise ValueError('Reference events require ordered nonnegative times and boolean presence')
            previous=event[0]
        self.reference_event_index=0


    def __copy__(self):
        clone=super().__copy__()
        clone.acquisition=copy.copy(self.acquisition) if self.acquisition is not None else None
        clone.phase_intervals=deque(self.phase_intervals,maxlen=self.phase_intervals.maxlen)
        return clone

    def bind_rail_interval(self,rail,end):
        if rail.time!=self.time or not math.isfinite(end) or end<self.time:
            raise ValueError('Rail and PLL must share the interval start')
        if self.rail_amplitude_hz:
            raise ValueError('Do not combine prescribed pulls with shared-rail ownership')
        bound=abs(rail.lo_sensitivity)*rail.droop_bound()
        if self.gains.free_hz-self.gains.kvco*self.filter.limit-bound-self.frequency_noise.bound_hz<=0:
            raise ValueError('Shared rail exceeds positive-frequency envelope')
        snapshot=copy.copy(rail);snapshot.pulse_clock=None
        self.rail_segment=(snapshot,end)

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic pulse-clock time required')
        while self.reference_event_index<len(self.reference_events):
            at,present=self.reference_events[self.reference_event_index]
            if at>time:break
            if not self._advance_observed(at):return False
            self.reference_event_index+=1
            # At an exact tie the scheduled reference edge precedes removal.
            # set_reference advances by zero and preserves oscillator/filter state.
            super().set_reference(present,at)
        return self._advance_observed(time)

    def _advance_observed(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic pulse-clock time required')
        if self.acquisition is not None:
            while self.next_reference<=time:
                if not self._advance_interval(self.next_reference):return False
                if self.present:self.acquisition.reference_edge(self.time,math.floor(self.phase/16))
                else:self.acquisition.tick(self.time)
                if self.acquisition.acquired and self.first_acquired is None:self.first_acquired=self.time
        ok=self._advance_interval(time)
        if self.acquisition is not None:self.acquisition.tick(self.time)
        return ok

    def _advance_interval(self,time):
        start=self.time
        if time>start and self.rail_segment is not None:
            # Preserve dynamic state without copying the ever-growing diagnostic
            # logs at every host/reference event.
            snapshot=object.__new__(type(self));snapshot.__dict__=self.__dict__.copy()
            snapshot.filter=copy.copy(self.filter);snapshot.gains=copy.copy(self.gains)
            # History is a bounded numerical observation cache, never a chain
            # of nested clock histories or an extra physical oscillator.
            snapshot.phase_intervals=deque(maxlen=512)
            snapshot.reference_history=[];snapshot.transitions=[]
            ok=super().advance(time)
            if self.time>start:self.phase_intervals.append((start,self.time,snapshot))
            return ok
        return super().advance(time)

    def observed_phase(self,times):
        result=[]
        for at in times:
            if not math.isfinite(at) or at>self.time:
                raise ValueError('Phase observation requires committed clock time')
            if at==self.time:
                result.append(self.phase);continue
            segment=next((entry for entry in reversed(self.phase_intervals)
                          if entry[0]<=at<=entry[1]),None)
            if segment is None:raise ValueError('Phase observation outside retained history')
            replay=copy.copy(segment[2])
            # Evaluate only an already committed, known forcing interval.
            if not super(RailDrivenPulsePLL,replay).advance(at):
                raise ClockQualificationError('Historical clock interval left compliance')
            result.append(replay.phase)
        return np.asarray(result)

    def set_supply(self,*args,**kwargs):
        if self.rail_segment is not None:
            raise ValueError('Shared rail owns supply forcing')
        return super().set_supply(*args,**kwargs)

    def rail_frequency(self,time):
        if self.rail_segment is None:return super().rail_frequency(time)
        rail,end=self.rail_segment
        tolerance=2*max(math.ulp(time),math.ulp(end),math.ulp(rail.time))
        if time<rail.time-tolerance or time>end+tolerance:
            raise ValueError('Pulse PLL query outside known rail interval')
        dt=max(0.,min(time,end)-rail.time)
        droop=rail.droop_at(dt)
        return -rail.lo_sensitivity*droop

    def rail_phase_integral(self,start,end):
        if self.rail_segment is None:return super().rail_phase_integral(start,end)
        if end<start:raise ValueError('Reversed rail interval')
        self.rail_frequency(start);self.rail_frequency(end)
        rail,_=self.rail_segment
        return -rail.lo_sensitivity*rail.droop_integral(start-rail.time,end-rail.time)


class ReferenceDrivenLO(SampledPLL):
    """Existing held-detector PI/VCO, compared only on supplied reference edges."""
    def __init__(self,edges,analytic=True,detector_phase_tones=(),**parameters):
        super().__init__(**parameters)
        if type(analytic) is not bool:raise ValueError('Boolean interval-solver selection required')
        self.analytic=analytic
        tones=tuple(tuple(float(v) for v in row) for row in detector_phase_tones)
        if any(len(row)!=3 or not all(math.isfinite(v) for v in row) or row[0]<=0 for row in tones):
            raise ValueError('Detector phase tones need positive frequency and finite cycle amplitude/phase')
        if not math.isfinite(sum(abs(a) for _,a,_ in tones)):
            raise ValueError('Unbounded detector phase disturbance')
        self.detector_phase_tones=tones
        self.reference_edges=tuple(edges);self.edge_index=bisect_right(self.reference_edges,self.time)
        if (any(not math.isfinite(t) or t<0 for t in self.reference_edges)
                or any(b<=a for a,b in zip(self.reference_edges,self.reference_edges[1:]))
                or any(not math.isclose(t*self.reference_hz,round(t*self.reference_hz),rel_tol=0.,abs_tol=1e-6) for t in self.reference_edges)):
            raise ValueError('LO reduction requires ordered nominal-grid reference edges; omissions are allowed')
        self.last_observation=None;self.first_lock_time=None;self.comparisons=0
        self.last_frequency_error=math.inf;self.last_lock_loss=None
        self.rail_segment=None
        self.next_detector=self.reference_edges[self.edge_index] if self.edge_index<len(self.reference_edges) else math.inf

    def detector_phase_noise(self,time):
        # Equivalent additive detector phase in reference cycles, not edge jitter.
        return sum(a*math.cos(2*math.pi*f*time+p) for f,a,p in self.detector_phase_tones)

    def rail_frequency(self,time):
        if self.rail_segment is None:return super().rail_frequency(time)
        rail,end=self.rail_segment
        tolerance=2*max(math.ulp(time),math.ulp(end),math.ulp(rail.time))
        if time<rail.time-tolerance or time>end+tolerance:
            raise ValueError('LO supply query outside current event interval')
        dt=max(0.,min(time,end)-rail.time)
        droop=rail.droop_at(dt)
        return -rail.lo_sensitivity*droop

    def _integrate(self,end):
        """Exact held-detector interval; retain RK for saturation boundaries."""
        dt=end-self.time
        if not dt:return
        slope=self.ki*self.detector_error if self.present else 0.
        control=self.kp*self.detector_error+self.integral if self.present else self.hold_voltage
        final_control=control+slope*dt
        if (not self.analytic or self.supply_trajectory is not None
                or min(control,final_control)<-self.rail or max(control,final_control)>self.rail):
            AutonomousPLL.advance(self,end);return
        if self.rail_segment is not None:
            rail,horizon=self.rail_segment
            self.rail_frequency(self.time);self.rail_frequency(end)  # Enforce known interval.
            begin=self.time-rail.time;finish=end-rail.time
            supply_integral=-rail.lo_sensitivity*rail.droop_integral(begin,finish)
            # Passive stored energy bounds every intermediate voltage excursion.
            supply_bound=rail.lo_sensitivity*rail.droop_bound()
        else:
            at_start=self.rail_amplitude_hz*math.exp(-(self.time-self.rail_epoch)/self.rail_tau)
            supply_integral=at_start*self.rail_tau*(-math.expm1(-dt/self.rail_tau))
            supply_bound=abs(at_start)
        minimum_frequency=self.free_hz+self.supply_shift_hz+self.kvco*min(control,final_control)-supply_bound-self.frequency_noise.bound_hz
        if minimum_frequency<=0:
            AutonomousPLL.advance(self,end);return
        cycles=(self.free_hz+self.supply_shift_hz)*dt+self.kvco*(control*dt+.5*slope*dt*dt)
        cycles+=supply_integral+self.frequency_noise.phase_integral(self.time,end)
        self.error+=self.reference_hz*dt-cycles/self.divider
        if abs(control)==self.rail and slope==0.:self.saturation_time+=dt
        self.integral+=slope*dt;self.time=end

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic LO time required')
        while self.next_detector<=time:
            tick=self.next_detector;self._integrate(tick)
            if self.present:
                self.detector_error=max(-.5,min(.5,self.error+self.detector_phase_noise(tick)));self.detector_updates+=1
                previous=self.last_observation
                # Frequency qualification uses two observed detector samples,
                # not the oscillator's true instantaneous derivative.
                frequency_error=(abs((self.detector_error-previous[1])/(tick-previous[0])) if previous else math.inf)
                valid=abs(self.detector_error)<self.lock_phase_cycles and frequency_error<self.lock_frequency_hz
                self.last_frequency_error=frequency_error
                if self.locked and not valid:
                    self.last_lock_loss=dict(time_s=tick,phase_error_cycles=self.detector_error,
                        frequency_error_hz=frequency_error,phase_limit_cycles=self.lock_phase_cycles,
                        frequency_limit_hz=self.lock_frequency_hz)
                self.good=self.good+1 if valid else 0;self.locked=self.good>=8
                self.last_observation=(tick,self.detector_error);self.comparisons+=1
                if self.locked and self.first_lock_time is None:self.first_lock_time=tick
            self.edge_index+=1
            self.next_detector=self.reference_edges[self.edge_index] if self.edge_index<len(self.reference_edges) else math.inf
        self._integrate(time)


class ClockQualificationError(ValueError):
    pass


class BehavioralChip:
    """Exclusive ownership, timed startup and finite directional host queues.

    Stream queues, source phase and frame quotas persist across transfer calls.
    Stop/reference loss explicitly discard pending bits and invalidate the epoch.
    """
    def __init__(self, assumptions):
        if any(not math.isfinite(v) or v < 0 for v in asdict(assumptions).values()):
            raise ValueError('Finite nonnegative assumptions required')
        if min(assumptions.host_clock_scale, assumptions.source_clock_scale, assumptions.h2d_clock_scale, assumptions.d2h_clock_scale) <= 0:
            raise ValueError('Positive clock scales required')
        if not 0<assumptions.rf_efficiency<=1 or not 0<=assumptions.host_data_rising_probability<=1:
            raise ValueError('Physical efficiency/activity interval required')
        if not 0<assumptions.minimum_supply_v<assumptions.supply_v:
            raise ValueError('Positive supply headroom required')
        self.a = assumptions
        self.time = 0.
        self.state = 'reset'
        self.epoch = 0
        self.resources = None
        self.ready_at = math.inf
        self.stream = None
        self.rf_stream=None
        self.rf_source=None
        self.parked_rf=None;self.rf_idle_phase=0.
        self.shared_rail=None
        self.reference=None
        self.lo_clock=None
        self.rf_sample_time=None
        self.transport_allocation='legacy'
        self.rf_clock=None;self.rf_clock_origin=None;self.rf_clock_config=None;self.rf_timing_recovery_required=False
        self.reference_return_measurements=None
        self.pending_common_reference_loss=None

    def configure_transport(self,allocation):
        if self.state!='reset' or self.stream is not None:
            raise ValueError('Transport allocation changes require stopped chip')
        if allocation not in ('legacy','exclusive'):raise ValueError('Unknown transport allocation')
        self.transport_allocation=allocation

    def attach_rf_timing(self,configuration):
        if self.state!='reset' or self.rf_stream is None or self.rf_clock is not None:
            raise ValueError('Attach converter timing once to stopped RF core')
        if self.resources.get('sample_clock_source')=='external_lo':
            raise ValueError('Direct LO divider cannot also consume the reference sample-clock path')
        timing=dict(configuration)
        amplitude=timing.pop('jitter_amplitude_s',0.)
        frequency=timing.pop('jitter_hz',1e6)
        phase=timing.pop('jitter_phase_rad',0.)
        absolute_time=timing.pop('absolute_time',False)
        pulse=None if self.shared_rail is None else self.shared_rail.pulse_clock
        reference_hz=timing.pop('reference_hz',pulse.reference if pulse is not None else 40e6)
        if not math.isfinite(reference_hz) or reference_hz<=0:raise ValueError('Positive converter reference required')
        if pulse is not None and (not absolute_time or not math.isclose(reference_hz*self.a.source_clock_scale,pulse.reference,rel_tol=1e-12)):
            raise ValueError('Pulse PLL and converter must share the absolute reference grid')
        if type(absolute_time) is not bool:raise ValueError('Boolean converter time-coordinate selection required')
        if timing:raise ValueError('Unknown converter timing configuration')
        if (not all(math.isfinite(v) for v in (amplitude,frequency,phase))
                or not 0<=amplitude<=.75e-9 or not 0<frequency<self.rf_stream.actual_sample_hz/2):
            raise ValueError('Converter jitter outside positive-delay envelope')
        divider=reference_hz/self.rf_stream.settings['sample_hz']
        if divider not in (1,2,3,4,8):raise ValueError('Unsupported reference divider')
        candidate=ReferenceSampleClock(reference_hz=reference_hz*self.a.source_clock_scale,jitter_bound_s=amplitude)
        self.rf_clock=candidate
        self.rf_clock_config=dict(reference_hz=reference_hz*self.a.source_clock_scale,amplitude=amplitude,frequency=frequency,phase=phase,divider=int(divider),absolute_time=absolute_time)

    def schedule_common_reference_loss(self,at):
        """External fault stimulus, consumed by the live host event scheduler."""
        if not math.isfinite(at) or at<self.time or self.pending_common_reference_loss is not None:
            raise ValueError('One future common-reference loss event required')
        if self.rf_clock is None or self.shared_rail is None or self.shared_rail.pulse_clock is None:
            raise ValueError('Common-reference clocks must be attached')
        self.pending_common_reference_loss=at

    def set_common_reference(self,present):
        """Apply an external REF_IN presence transition at the committed epoch.

        Event distribution only: this is not an on-chip instantaneous detector,
        host fault notification, or authorization to resume after missing edges.
        """
        pulse=None if self.shared_rail is None else self.shared_rail.pulse_clock
        if (type(present) is not bool or pulse is None or self.rf_clock is None
                or self.lo_clock is not None or self.reference is not None
                or pulse.reference_events or pulse.time!=self.time
                or self.shared_rail.time!=self.time):
            raise ValueError('Common reference requires synchronized exclusive clock ownership')
        if pulse.present!=self.rf_clock.present:
            raise ValueError('Reference branches disagree before common transition')
        if present==pulse.present:return dict(changed=False,cancelled_edge_s=None)
        pending=self.rf_clock.proposal
        pulse.set_reference(present,self.time)
        self.rf_clock.set_reference(present)
        if not present:
            self.rf_timing_recovery_required=True;self.reference_return_measurements=None
            if self.stream is not None:self.stream['next_source_time']=None
        else:
            self.reference_return_measurements=(None if pulse.acquisition is None else pulse.acquisition.measurements)
        return dict(changed=True,cancelled_edge_s=(pending.time if pending is not None and not present else None),
                    requires_explicit_recovery=self.rf_timing_recovery_required)

    def rearm_after_reference(self):
        """Explicit converter rearm after fresh counted acquisition, not phase certification."""
        rail=self.shared_rail;core=self.parked_rf
        pulse=None if rail is None else rail.pulse_clock
        monitor=None if pulse is None else pulse.acquisition
        if (self.state!='reset' or self.stream is not None or not self.rf_timing_recovery_required
                or core is None or core.analog_time!=self.time or pulse is None
                or pulse.time!=self.time or not pulse.present or pulse.fault is not None
                or self.rf_clock is None or not self.rf_clock.present or self.rf_clock.index is not None
                or monitor is None or not monitor.acquired or self.reference_return_measurements is None):
            raise ValueError('Recovery requires stopped retained state and fresh reference acquisition')
        # Discard the first possibly partial window after return, then require
        # a full run of qualified windows. No clock/analog state is reset.
        if monitor.measurements-self.reference_return_measurements<monitor.required+1:
            raise ValueError('Insufficient post-return acquisition windows')
        self.rf_clock.arm(self.time,self.rf_clock_config['divider'])
        self.rf_timing_recovery_required=False
        return dict(rearmed_at_s=self.time,next_reference_index=self.rf_clock.index,
                    epoch=self.epoch,phase_quality_certified=False)

    def advance_reference_gap(self,end,*,maximum_step_s=25e-9):
        """Stopped held-DAC evolution while converters remain explicitly disarmed.

        Returning REF_IN may reacquire the PLL here; this never rearms conversion
        or releases the recovery guard. No host service or converter charge is
        manufactured during the interval.
        """
        core=self.parked_rf
        rail=self.shared_rail
        if (self.state!='reset' or self.stream is not None or not self.rf_timing_recovery_required
                or core is None or core.analog_time is None or not core.external_substeps
                or self.rf_clock is None or self.rf_clock.index is not None
                or rail is None or rail.pulse_clock is None
                or getattr(core,'shared_pulse_clock',None) is not rail.pulse_clock
                or not self.rf_clock_config['absolute_time']):
            raise ValueError('Reference gap requires retained quadrature RF and disarmed shared clocks')
        if (not math.isfinite(end) or end<self.time or not math.isfinite(maximum_step_s)
                or not 0<maximum_step_s<=1/core.actual_sample_hz):
            raise ValueError('Finite forward interval and bounded analog step required')
        while core.analog_time<end:
            target=min(end,core.analog_time+maximum_step_s)
            if target<=core.analog_time:raise ValueError('Analog step below time resolution')
            if target>self.time:
                rail.advance(target);self.time=target
            core.advance_analog_hold(target)
        return dict(time_s=self.time,committed_samples=core.index,held_dac=core.held_dac,
                    recovery_required=self.rf_timing_recovery_required)

    def _forecast_rf_edge(self):
        clock=self.rf_clock;configuration=self.rf_clock_config
        reference=clock.origin+clock.index*clock.period
        jitter=configuration['amplitude']*math.sin(2*math.pi*configuration['frequency']*reference+configuration['phase'])
        return clock.forecast(lambda t:clock.nominal_v,maximum_slew_v_per_s=0.,jitter_s=jitter)

    def timed_rf_callbacks(self):
        if self.state!='active' or self.rf_stream is None or self.rf_clock is None or self.stream is not None:
            raise ValueError('Bind timed callbacks once before active RF transport')
        clock=self.rf_clock;origin=self.time;epoch=self.epoch;core=self.rf_stream;base=core.index;source=self.rf_source
        if clock.index is None:
            clock.arm(origin,self.rf_clock_config['divider']);self.rf_clock_origin=origin
        def check_event(index):
            if self.state!='active' or self.epoch!=epoch or self.rf_stream is not core or core.index!=base+index:
                raise ValueError('Stale converter clock event')
        def forecast(index):
            check_event(index)
            if not clock.present:return math.inf
            return self._forecast_rf_edge().time-origin
        def produce(index):
            check_event(index)
            proposal=clock.proposal
            if proposal is None:raise ValueError('Converter event requires current forecast')
            clock.commit(proposal,proposal.time)
            self.rf_sample_time=proposal.time if self.rf_clock_config['absolute_time'] else proposal.time-self.rf_clock_origin
            try:return source(index)
            finally:self.rf_sample_time=None
        return dict(rx_event_time=forecast,rx_source=produce)

    def _advance_timed_rf_idle(self,end,reference_loss):
        core=self.parked_rf
        while True:
            proposal=self._forecast_rf_edge()
            target=min(end,proposal.time)
            clock_loss=self._lo_to(target)
            if clock_loss is not None:target=clock_loss
            if self.shared_rail is not None:self.shared_rail.advance(target)
            self.time=target
            if clock_loss is not None or (reference_loss is not None and target>=end):
                self.state='fault';self.ready_at=math.inf
                if clock_loss is not None:raise ClockQualificationError('Observed LO qualification lost')
                raise ReferenceLossError('Reference pulse timeout')
            if self.shared_rail is not None and self.shared_rail.voltage<self.a.minimum_supply_v:
                self.state='fault';self.ready_at=math.inf
                raise SupplyRangeError('Shared rail below model range during timed idle')
            if target>=end:break
            self.rf_clock.commit(proposal,proposal.time)
            self.rf_sample_time=proposal.time if self.rf_clock_config['absolute_time'] else proposal.time-self.rf_clock_origin
            try:self._rf_step(core,[0j])
            except SupplyRangeError:
                self.state='fault';self.ready_at=math.inf
                raise
            finally:self.rf_sample_time=None
        if (self.state=='acquiring' and self.time>=self.ready_at
                and (self.reference is None or self.reference.qualified(self.time))
                and (self.lo_clock is None or self.lo_clock.locked)):
            self.state='active'

    def attach_reference(self,edges,**parameters):
        if self.state!='reset' or self.reference is not None:
            raise ValueError('Attach reference monitor once while stopped')
        self.reference=ReferencePresence(edges,**parameters)

    def attach_lo_clock(self,noise_rms_hz=0.,noise_seed=830,noise_tones=None,**parameters):
        if self.state!='reset' or self.time!=0 or self.reference is None or self.lo_clock is not None:
            raise ValueError('Attach LO once at time zero after external reference')
        if self.resources is None or self.resources['engine']!='rf':raise ValueError('RF owner required for LO')
        if self.resources.get('sample_clock_source')=='external_lo':
            raise ValueError('Direct LO configuration must bypass autonomous synthesis')
        from oscillator_noise import FrequencyNoise
        if noise_tones is not None and noise_rms_hz!=0.:raise ValueError('Choose explicit tones or seeded RMS noise')
        candidate=ReferenceDrivenLO(self.reference.edges,**parameters)
        candidate.set_noise(0.,FrequencyNoise(noise_tones) if noise_tones is not None else FrequencyNoise.seeded(noise_rms_hz,seed=noise_seed))
        self.lo_clock=candidate

    def _lo_to(self,end):
        clock=self.lo_clock
        if clock is None:return None
        if self.shared_rail is not None:
            if self.shared_rail.time>clock.time:raise ValueError('Rail advanced beyond LO coupling history')
            clock.rail_segment=(copy.copy(self.shared_rail),end)
        while clock.next_detector<=end:
            clock.advance(clock.next_detector)
            if self.state=='active' and not clock.locked:return clock.time
        clock.advance(end)
        return None

    def attach_shared_rail(self,**parameters):
        if self.state!='reset' or self.shared_rail is not None:
            raise ValueError('Attach shared rail once while stopped')
        self.shared_rail=SharedRail(time=self.time,**parameters)

    def attach_pulse_rf(self,core):
        if self.resources is not None and self.resources.get('sample_clock_source')=='external_lo':
            raise ValueError('Direct LO configuration must bypass autonomous synthesis')
        rail=self.shared_rail
        if rail is None or rail.pulse_clock is None or self.lo_clock is not None:
            raise ValueError('RF requires one shared-rail pulse clock owner')
        if core.mixer_phase_source is not None:
            raise ValueError('RF mixer already has a phase owner')
        clock=rail.pulse_clock
        if self.rf_clock is not None and (not self.rf_clock_config['absolute_time'] or not math.isclose(1/self.rf_clock.period,clock.reference,rel_tol=1e-12)):
            raise ValueError('Pulse PLL and converter must share the absolute reference grid')
        def phase(times):
            # Analog phase continues while unqualified; conversion admission is
            # checked separately by the chip, including before load accounting.
            return -2*math.pi*(clock.observed_phase(times)-clock.rate*np.asarray(times))
        core.mixer_phase_source=phase
        core.shared_pulse_clock=clock

    def _rf_step(self,core,values):
        phase=0. if self.lo_clock is None else -2*math.pi*self.lo_clock.divider*self.lo_clock.error
        times=None if self.rf_sample_time is None else [self.rf_sample_time]
        if self.shared_rail is None:return core.process(values,supply_phase_rad=phase,sample_times_s=times)
        if len(values)!=1:raise ValueError('Coupled RF needs one chronological converter event')
        rail=self.shared_rail
        if rail.pulse_clock is not None:
            if (self.lo_clock is not None or getattr(core,'shared_pulse_clock',None) is not rail.pulse_clock
                    or times is None or abs(times[0]-rail.time)>4*max(math.ulp(times[0]),math.ulp(rail.time))):
                raise ValueError('Pulse RF requires exclusive phase ownership and absolute converter time')
            # Scheduler reconstructs origin + relative event time; normalize only
            # its floating-point roundoff to the committed absolute endpoint.
            times=[rail.time]
            monitor=rail.pulse_clock.acquisition
            if monitor is not None and not monitor.acquired:
                raise ClockQualificationError('Shared pulse clock not count-qualified')
        rail.converter()
        if rail.voltage<self.a.minimum_supply_v:raise SupplyRangeError('Shared rail below model range before conversion')
        # With an LO attached, its phase already includes this rail's VCO pull.
        return core.process(values,supply_scale=1+(rail.voltage/rail.nominal-1)*rail.rf_gain_fraction,
            supply_phase_rad=phase if self.lo_clock is not None or rail.pulse_clock is not None else rail.phase,sample_times_s=times)


    def configure(self, word):
        if self.state != 'reset':
            raise ValueError('Stop before resource changes')
        resources = decode_resource_word(word)
        if resources['engine'] == 'none':
            raise ValueError('Choose one payload owner')
        self.resources = resources
        self.rf_stream=None;self.rf_source=None

    def configure_numeric(self, *, engine, timing=None, rf=None):
        """Behavioral sideband configuration; serialized ABI mapping is pending."""
        if self.state != 'reset':
            raise ValueError('Stop before resource changes')
        if engine == 'wire' and timing is not None and rf is None:
            settings=validate_wire_timing(**timing)
        elif engine == 'rf' and rf is not None and timing is None:
            settings=validate_rf_settings(**rf)
        else:
            raise ValueError('Settings must match exclusive engine')
        self.configure(encode_resource_word(engine=engine))
        self.resources.update(settings)

    def attach_rf_stream(self,input_source,*,offset_hz=0.,seed=81,**impairments):
        if self.state!='reset' or self.resources is None or 'sample_hz' not in self.resources or not callable(input_source):
            raise ValueError('Configured idle numeric RF resource required')
        settings={key:self.resources[key] for key in ('sample_hz','tx_cutoff_hz','rx_cutoff_hz','rx_gain','rx_filter_order','converter_bits')}
        settings.update({key:self.resources[key] for key in ('sample_clock_source','lo_hz','lo_divider') if key in self.resources})
        if self.parked_rf is not None:raise ValueError('Resume retained RF state; replacing it would erase physical history')
        core=SampledRFStream(settings,offset_hz=offset_hz,seed=seed,clock_scale=self.a.source_clock_scale,**impairments)
        self._bind_rf_stream(core,input_source,settings)

    def _bind_rf_stream(self,core,input_source,settings):
        epoch=self.epoch;base=None
        def produce(index):
            nonlocal base
            if base is None and self.state=='active' and self.epoch==epoch and index==0:
                if self.parked_rf is core:
                    self.parked_rf=None
                base=core.index
            if self.state!='active' or self.epoch!=epoch or base is None or core.index!=base+index:
                raise ValueError('Stale or misaligned RF sample event')
            value=self._rf_step(core,[input_source(index)])[0]
            bits=settings['converter_bits'];scale=1<<(bits-1);mask=(1<<bits)-1
            return (int(round(value.real*scale))&mask) | ((int(round(value.imag*scale))&mask)<<bits)
        self.rf_stream=core;self.rf_source=produce

    def resume_rf_stream(self,input_source):
        if self.state!='reset' or self.parked_rf is None or not callable(input_source):
            raise ValueError('Stopped retained RF core required')
        if self.rf_timing_recovery_required:raise ValueError('Timed fault recovery requires missing-edge/analog recovery model')
        core=self.parked_rf
        if self.resources is None or self.resources.get('engine')!='rf' or any(self.resources.get(k)!=v for k,v in core.settings.items()):
            raise ValueError('Retained RF configuration mismatch; physical retune is not implemented')
        self._bind_rf_stream(core,input_source,core.settings)


    def start(self):
        if self.rf_timing_recovery_required:raise ValueError('Timed fault recovery requires missing-edge/analog recovery model')
        if self.resources is None or self.state != 'reset':
            raise ValueError('Configured reset state required')
        if self.lo_clock is not None and self.resources['engine']!='rf':
            raise ValueError('LO adapter currently qualifies RF ownership only')
        if self.parked_rf is not None and self.resources['engine']=='rf' and self.rf_source is None:
            raise ValueError('Resume retained RF before arming')
        self.state = 'acquiring'
        if self.reference is not None:self.reference.armed_at=self.time
        if self.lo_clock is not None:
            self.lo_clock.set_reference(True,self.time);self.lo_clock.last_observation=None
        self.ready_at = self.time + self.a.startup_s

    def advance(self, end):
        if self.state=='fault':raise ValueError('Stop faulted chip before advancing')
        if self.rf_timing_recovery_required:raise ValueError('Timed fault recovery requires missing-edge/analog recovery model')
        if self.parked_rf is not None and self.parked_rf.timed_mode and self.rf_clock is None and end!=self.time:
            raise ValueError('Timed RF idle continuation requires explicit clock events; uniform substitution forbidden')
        if not math.isfinite(end) or end < self.time:
            raise ValueError('Monotonic event time required')
        if self.stream is not None and end!=self.time:
            raise ValueError('Advance active stream through transfer, or stop first')
        loss=None
        if self.reference is not None and (self.state in ('acquiring','active') or (self.parked_rf is not None and self.rf_clock is not None)):
            loss=self.reference.fault_between(self.time,end)
            if loss is not None:end=loss
        if self.parked_rf is not None and self.rf_clock is not None:
            if self.rf_clock.index is None:raise ValueError('Stopped timed RF requires previously armed converter clock')
            self._advance_timed_rf_idle(end,loss)
            return
        if self.lo_clock is not None:
            self._advance_with_lo(end,loss)
            return
        if self.parked_rf is not None:
            elapsed=self.rf_idle_phase+(end-self.time)*self.parked_rf.actual_sample_hz
            ticks=max(0,math.ceil(elapsed-1e-9))
            if self.shared_rail is None:self.parked_rf.process(np.zeros(ticks,complex))
            else:
                for tick in range(ticks):
                    event_time=self.time+(-self.rf_idle_phase+tick)/self.parked_rf.actual_sample_hz
                    self.shared_rail.advance(event_time)
                    try:self._rf_step(self.parked_rf,[0j])
                    except SupplyRangeError:
                        self.time=event_time;self.rf_idle_phase=0.
                        self.state='fault';self.ready_at=math.inf
                        raise
            self.rf_idle_phase=elapsed-ticks
        if self.shared_rail is not None:self.shared_rail.advance(end)
        self.time = end
        if loss is not None:
            self.state='fault';self.ready_at=math.inf
            raise ReferenceLossError('Reference pulse timeout')
        if (self.state == 'acquiring' and end >= self.ready_at
                and (self.reference is None or self.reference.qualified(end))):
            self.state = 'active'

    def _advance_with_lo(self,end,reference_loss):
        start=self.time;initial_phase=self.rf_idle_phase;done=0;clock_loss=None
        core=self.parked_rf
        while True:
            converter=(start+(-initial_phase+done)/core.actual_sample_hz) if core is not None else math.inf
            target=min(end,converter)
            clock_loss=self._lo_to(target)
            if clock_loss is not None:target=clock_loss
            if self.shared_rail is not None:self.shared_rail.advance(target)
            self.time=target
            if clock_loss is not None or target>=end:break
            try:self._rf_step(core,[0j])
            except SupplyRangeError:
                self.rf_idle_phase=0.;self.state='fault';self.ready_at=math.inf
                raise
            done+=1
        if core is not None:self.rf_idle_phase=initial_phase+(self.time-start)*core.actual_sample_hz-done
        if clock_loss is not None or reference_loss is not None:
            self.state='fault';self.ready_at=math.inf
            if clock_loss is not None:raise ClockQualificationError('Observed LO qualification lost')
            raise ReferenceLossError('Reference pulse timeout')
        if (self.state=='acquiring' and self.time>=self.ready_at and self.lo_clock.locked
                and self.reference.qualified(self.time)):
            self.state='active'

    def stop(self):
        if self.state=='fault' and self.rf_clock is not None:self.rf_timing_recovery_required=True
        discarded=dict(rx_bits=self.stream['occupancy'] if self.stream else 0,
                       tx_bits=self.stream['tx_bits'] if self.stream else 0)
        if self.stream is not None and 'host_captured' in self.stream:
            discarded['host_staged_bits']=self.stream['host_captured']-self.stream['host_committed']
        if self.stream is not None and self.stream.get('rx_cancel') is not None:
            discarded['rx_source']=self.stream['rx_cancel']()
        if self.rf_stream is not None and self.parked_rf is not self.rf_stream:
            self.parked_rf=self.rf_stream
            self.rf_idle_phase=((self.time-self.stream['origin'])*self.rf_stream.actual_sample_hz-self.stream['sample_index']-self.stream.get('source_phase',0.)
                                if self.stream is not None else 0.)
        self.stream=None
        self.rf_stream=None;self.rf_source=None
        self.state = 'reset'
        self.ready_at = math.inf
        self.epoch += 1
        if self.lo_clock is not None:self.lo_clock.set_reference(False,self.time)
        return discarded

    def lose_reference(self):
        return self.stop()

    def receive(self, **kwargs):
        return self.transfer(directions=('rx',), **kwargs)

    def transfer(self, *, mode, source_hz, sample_bits, frames=128, depth_bits=2048,
                 host_pause_frames=0, epoch, directions=('rx','tx'), tx_prefill_bits=512,
                 feedback=False, feedback_stop_after=None, rx_source=None, tx_source=None, tx_prefill_value=0, rx_event_time=None, rx_valid=None, rx_cancel=None, host_block_words=1, host_cdc_read_hz=None, host_cdc_phase=0.,host_word_observer=None,tx_word_observer=None,tx_reference_pacing=False,tx_reference_ticks=None):
        if tx_reference_ticks is not None and (not tx_reference_pacing or not callable(tx_reference_ticks)):
            raise ValueError('Reference-edge observer requires reference pacing')
        if type(tx_reference_pacing) is not bool or (tx_reference_pacing and ('tx' not in directions or feedback)):
            raise ValueError('Reference pacing requires TX without occupancy feedback')
        if tx_reference_pacing and not math.isclose(self.a.source_clock_scale,self.a.host_clock_scale*self.a.d2h_clock_scale,rel_tol=1e-12):
            raise ValueError('Reference pacing requires the declared TX/D2H frequency relationship')
        if host_word_observer is not None and not callable(host_word_observer):raise ValueError('Callable host word observer required')
        if tx_word_observer is not None and (not callable(tx_word_observer) or tx_source is None or 'tx' not in directions):
            raise ValueError('TX observation requires a concrete enabled source and callable observer')
        if type(host_block_words) is not int or host_block_words not in (1,8):
            raise ValueError('Host block width must be one or eight words')
        if host_cdc_read_hz is not None and (host_block_words!=8 or not math.isfinite(host_cdc_read_hz) or host_cdc_read_hz<=0 or 'tx' not in directions):
            raise ValueError('CDC requires eight-word TX and a positive destination clock')
        if not math.isfinite(host_cdc_phase) or not 0<=host_cdc_phase<1:
            raise ValueError('CDC destination phase must be in [0,1) cycles')
        if self.rf_clock is not None and (rx_event_time is None or rx_source is None):
            raise ValueError('Timed RF transport requires bound clock/source callbacks')
        if rx_source is None and 'rx' in directions and self.rf_source is not None:rx_source=self.rf_source
        full_activity=self.shared_rail is not None and self.shared_rail.full_host_activity
        if full_activity and (feedback or ('tx' in directions and tx_source is None) or ('rx' in directions and rx_source is None)):
            raise ValueError('Complete host activity requires concrete payload sources and a defined non-feedback header')
        if self.state != 'active' or epoch != self.epoch:
            raise ValueError('Active current-epoch stream required')
        if not directions or len(set(directions))!=len(directions) or any(d not in ('rx','tx') for d in directions):
            raise ValueError('Distinct RX/TX directions required')
        if any(not self.resources[d+'_enabled'] for d in directions):
            raise ValueError('Requested direction disabled')
        if len(directions)>1 and self.resources['pad_path']=='bidirectional':
            raise ValueError('Shared bidirectional pad cannot transmit and receive payload simultaneously')
        if type(tx_prefill_bits) is not int or not 0<=tx_prefill_bits<=depth_bits:
            raise ValueError('TX prefill must fit finite queue')
        if (not math.isfinite(source_hz) or source_hz <= 0 or type(sample_bits) is not int or sample_bits <= 0
                or type(frames) is not int or frames < 1 or type(depth_bits) is not int or depth_bits < sample_bits
                or type(host_pause_frames) is not int or host_pause_frames < 0):
            raise ValueError('Invalid stream geometry')
        if type(feedback) is not bool or (feedback and 'tx' not in directions):
            raise ValueError('Feedback requires TX service')
        if feedback_stop_after is not None and (type(feedback_stop_after) is not int or feedback_stop_after<0):
            raise ValueError('Nonnegative report-loss frame required')
        if 'sample_hz' in self.resources:
            if source_hz!=self.resources['sample_hz'] or sample_bits!=2*self.resources['converter_bits']:
                raise ValueError('Stream must use configured RF clock and I/Q precision')
        elif 'clock_source' in self.resources:
            if not math.isclose(source_hz,self.resources['line_rate_bps']/10,rel_tol=1e-12) or sample_bits!=10:
                raise ValueError('Stream must use configured wired word clock and width')
        if rx_source is not None and (not callable(rx_source) or 'rx' not in directions):
            raise ValueError('RX payload source requires enabled receive service')
        if rx_valid is not None and (not callable(rx_valid) or rx_source is None):
            raise ValueError('RX validity requires a payload source')
        if rx_cancel is not None and (not callable(rx_cancel) or rx_source is None):
            raise ValueError('RX cancellation requires a payload source')
        if tx_source is not None and (not callable(tx_source) or 'tx' not in directions):
            raise ValueError('TX word source requires enabled transmit service')
        if type(tx_prefill_value) is not int or not 0<=tx_prefill_value<(1<<tx_prefill_bits):
            raise ValueError('TX prefill value must fit prefill bit count')
        if rx_event_time is not None and (not callable(rx_event_time) or
                (directions!=('rx',) and not (self.resources['engine']=='rf' and directions==('rx','tx') and self.rf_stream is not None))):
            raise ValueError('Timed source requires RX-only service or paired live RF conversion')
        owner=('iq' if self.resources['engine']=='rf' else 'wire') if self.transport_allocation=='exclusive' else None
        plan = slots(mode, self.resources['frame_words'],owner=owner)
        name = 'iq' if self.resources['engine'] == 'rf' else 'wire'
        host_hz = (250e6 if mode == 0 else 312.5e6) * self.a.host_clock_scale
        rate = source_hz * self.a.source_clock_scale
        signature=(mode,source_hz,sample_bits,depth_bits,tuple(directions),tx_prefill_bits,host_pause_frames,feedback,feedback_stop_after,rx_source,tx_source,tx_prefill_value,rx_event_time,rx_valid,rx_cancel,host_block_words,host_cdc_read_hz,host_cdc_phase,tx_word_observer,tx_reference_pacing,tx_reference_ticks)
        if self.stream is not None and self.stream['signature']!=signature:
            raise ValueError('Stop before changing stream geometry or prefill')
        if self.stream is None:
            initial=tx_prefill_bits if 'tx' in directions else 0
            self.stream=dict(signature=signature,origin=self.time,frame=0,
                occupancy=0,produced=0,returned=0,high=0,sample_index=0,rx_slot=0,tx_slot=0,rx_quota=0,tx_quota=0,
                tx_bits=initial,tx_min=initial,tx_high=initial,tx_in=0,tx_out=0,
                reports=deque(),snapshot=None,last_report=None,reports_received=0,quota_phase=0.,last_source_time=-math.inf,next_source_time=None)
            self.stream['source_phase']=max(0.,-self.rf_idle_phase) if self.parked_rf is not None and self.rf_source is not None else 0.
            self.stream['rx_cancel']=rx_cancel
            if rx_source is not None:self.stream.update(rx_buffer=0,rx_words=[])
            if tx_source is not None:self.stream.update(tx_buffer=tx_prefill_value,tx_samples=[])
        state=self.stream
        if host_block_words==8 and 'host_blocks' not in state:
            state.update(host_blocks=deque(),host_collect=[],host_captured=0,host_committed=0,host_block_high=0)
        if host_cdc_read_hz is not None and 'host_cdc' not in state:
            state.update(host_cdc=BlockFIFO(),cdc_wr_index=0,cdc_rd_index=0,cdc_bits=0,cdc_high=0,cdc_written=0)
        occupancy,produced,returned,high=(state[k] for k in ('occupancy','produced','returned','high'))
        sample_index=state['sample_index']
        rx_slot,tx_slot,quota,tx_quota=(state[k] for k in ('rx_slot','tx_slot','rx_quota','tx_quota'))
        tx_bits,tx_min,tx_high,tx_in,tx_out=(state[k] for k in ('tx_bits','tx_min','tx_high','tx_in','tx_out'))
        nominal_host=250e6 if mode==0 else 312.5e6
        nominal_words_per_frame=source_hz*sample_bits*len(plan)/(10*nominal_host)
        fault = None
        rx_hz=host_hz*self.a.d2h_clock_scale
        tx_hz=host_hz*self.a.h2d_clock_scale
        end_frame=state['frame']+frames
        end=end_frame*len(plan)/host_hz
        # Ordered source, D2H and H2D events. Conservative ties consume TX
        # before a simultaneous host write. Slot counters preserve frame phase.
        reference_checked=self.time
        while True:
            if rx_event_time is None:source_time=(sample_index+state['source_phase'])/rate
            else:
                if state['next_source_time'] is None:
                    candidate=rx_event_time(sample_index)
                    missing_converter=(candidate==math.inf and self.rf_clock is not None and not self.rf_clock.present)
                    if not missing_converter and (not math.isfinite(candidate) or candidate<0 or candidate<=state['last_source_time']):
                        raise ValueError('Recovered sample times must be finite and strictly increasing')
                    state['next_source_time']=candidate
                source_time=state['next_source_time']
            watchdog_time=math.inf
            if self.rf_clock is not None and not self.rf_clock.present and self.shared_rail is not None:
                pulse=self.shared_rail.pulse_clock
                if pulse is not None:
                    last=pulse.reference_history[-1][0] if pulse.reference_history else 0.
                    timeout=pulse.acquisition.watchdog if pulse.acquisition is not None else 100e-9
                    # Explicit independent timer event; no converter or GPIO
                    # edge is required to observe the strict timeout boundary.
                    watchdog_time=math.nextafter(last+timeout,math.inf)-state['origin']
            now,kind=min((source_time,0),
                (rx_slot/rx_hz if 'rx' in directions or feedback else math.inf,1),
                (tx_slot/tx_hz if 'tx' in directions else math.inf,2),
                (state['reports'][0][0] if state['reports'] else math.inf,3),
                ((7+8*state['cdc_wr_index'])/tx_hz if host_cdc_read_hz is not None else
                 state['host_blocks'][0][0] if host_block_words==8 and state['host_blocks'] else math.inf,4),
                ((state['cdc_rd_index']+host_cdc_phase)/host_cdc_read_hz if host_cdc_read_hz is not None else math.inf,5),
                (self.pending_common_reference_loss-state['origin'] if self.pending_common_reference_loss is not None else math.inf,-1),
                (watchdog_time,-2))
            reference_loss=None
            if self.reference is not None:
                target=state['origin']+min(now,end)
                reference_loss=self.reference.fault_between(reference_checked,target)
                if reference_loss is not None:now=reference_loss-state['origin']
                reference_checked=target
            clock_loss=self._lo_to(state['origin']+min(now,end))
            if clock_loss is not None:
                now=clock_loss-state['origin'];fault='lo_unqualified';break
            if reference_loss is not None:
                fault='reference_lost';break
            if now>end or (now==end and kind!=-2):
                now=end;break
            if self.shared_rail is not None:
                self.shared_rail.advance(state['origin']+now)
                if self.shared_rail.voltage<self.a.minimum_supply_v:
                    fault='shared_supply_low';break
            if kind==-1:
                self.time=state['origin']+now
                self.set_common_reference(False)
                self.pending_common_reference_loss=None
                continue
            if kind==-2:
                fault='reference_lost';break
            if kind==0:
                if 'tx' in directions and tx_bits<sample_bits:
                    fault='underflow';break
                if 'rx' not in directions and self.rf_source is not None:
                    try:self.rf_source(sample_index)  # Advance analog TX even without RX host service.
                    except SupplyRangeError:
                        fault='shared_supply_low';break
                    except ClockQualificationError:
                        fault='lo_unqualified';break
                if 'rx' in directions:
                    valid=True if rx_valid is None else rx_valid(sample_index)
                    if type(valid) is not bool:raise ValueError('RX validity must be boolean')
                    if valid and occupancy+sample_bits>depth_bits:
                        fault='overflow';break
                    if rx_source is not None:
                        try:value=rx_source(sample_index)
                        except SupplyRangeError:
                            fault='shared_supply_low';break
                        except ClockQualificationError:
                            fault='lo_unqualified';break
                        if type(value) is not int or not 0<=value<(1<<sample_bits):
                            raise ValueError('RX sample must fit configured unsigned packing width')
                        if valid:state['rx_buffer']|=value<<occupancy
                    if valid:
                        occupancy+=sample_bits;produced+=sample_bits;high=max(high,occupancy)
                    else:state['invalid_rx_events']=state.get('invalid_rx_events',0)+1
                if 'tx' in directions:
                    if tx_bits<sample_bits:
                        fault='underflow';break
                    if tx_source is not None:
                        emitted_word=state['tx_buffer']&((1<<sample_bits)-1)
                        state['tx_samples'].append(emitted_word)
                        state['tx_buffer']>>=sample_bits
                        if tx_word_observer is not None:tx_word_observer(state['origin']+now,emitted_word)
                    tx_bits-=sample_bits;tx_out+=sample_bits;tx_min=min(tx_min,tx_bits)
                state['next_source_time']=None
                state['last_source_time']=source_time
                sample_index+=1
            elif kind==1:
                frame,slot=divmod(rx_slot,len(plan))
                rail_word=0 if full_activity or host_word_observer is not None else None
                if slot==0:
                    quota=min(plan.count(name),occupancy//10) if frame>=host_pause_frames else 0
                    if feedback:state['snapshot']=(now,math.ceil(tx_bits*255/depth_bits),self.epoch)
                    if full_activity or host_word_observer is not None:state['rx_header']=stream_metadata(quota if name=='wire' else 0,quota if name=='iq' else 0,frame%64)
                if (full_activity or host_word_observer is not None) and slot<5:rail_word=state['rx_header'][slot]
                if slot==4 and feedback and (feedback_stop_after is None or frame<feedback_stop_after):
                    # Proposed occupancy use of the existing 8-bit header argument.
                    # Frame serialization plus two frame periods of external latency.
                    if len(state['reports'])>=16:
                        fault='telemetry_overflow';break
                    state['reports'].append((now+2*len(plan)/rx_hz,*state['snapshot']))
                if plan[slot]==name and quota:
                    if rx_source is not None:
                        rail_word=state['rx_buffer']&1023
                        state['rx_words'].append(rail_word)
                        state['rx_buffer']>>=10
                    occupancy-=10;returned+=10;quota-=1
                if host_word_observer is not None:host_word_observer(state['origin']+now,rail_word)
                if self.shared_rail is not None:self.shared_rail.host_word(rail_word)
                rx_slot+=1
                if self.shared_rail is not None and self.shared_rail.voltage<self.a.minimum_supply_v:
                    fault='shared_supply_low';break
            elif kind==2:
                frame,slot=divmod(tx_slot,len(plan))
                input_word=0
                if slot==0:
                    tx_quota=min(plan.count(name),math.floor((frame+1)*nominal_words_per_frame)-math.floor(frame*nominal_words_per_frame))
                    if tx_reference_pacing:
                        # External producer counts already elapsed D2H edges;
                        # no consumer occupancy or future reference edges used.
                        ticks=(math.floor(now*rx_hz) if tx_reference_ticks is None
                               else tx_reference_ticks(state['origin']+now))
                        if type(ticks) is not int or ticks<state.get('reference_ticks',0):
                            raise ValueError('Monotonic nonnegative reference-edge count required')
                        state['reference_ticks']=ticks
                        ratio=Fraction(str(source_hz))*sample_bits/(10*Fraction(str(nominal_host)))
                        eligible=(ticks*ratio.numerator)//ratio.denominator
                        supplied=(state['host_captured'] if host_block_words==8 else tx_in)//10
                        tx_quota=min(plan.count(name),max(0,eligible-supplied))
                    if feedback:
                        report=state['last_report']
                        age=now-(report[0] if report is not None else 0.)
                        if age>8*len(plan)/rx_hz:
                            fault='stale_feedback';break
                        if report is not None:
                            observed=report[1]*depth_bits/255
                            correction=(tx_prefill_bits-observed)/120
                            state['quota_phase']+=max(0.,min(plan.count(name),nominal_words_per_frame+correction))
                            tx_quota=math.floor(state['quota_phase']);state['quota_phase']-=tx_quota
                    if frame<host_pause_frames:tx_quota=0
                    if full_activity:state['tx_header']=stream_metadata(tx_quota if name=='wire' else 0,tx_quota if name=='iq' else 0,frame%64)
                if full_activity and slot<5:input_word=state['tx_header'][slot]
                if plan[slot]==name and tx_quota:
                    if host_block_words==1 and tx_bits+10>depth_bits:
                        fault='tx_overflow';break
                    value=0
                    if tx_source is not None:
                        value=tx_source(state['host_captured']//10 if host_block_words==8 else tx_in//10)
                        if type(value) is not int or not 0<=value<1024:
                            raise ValueError('TX host payload must fit ten bits')
                        input_word=value
                    if host_block_words==8:
                        state['host_collect'].append(value);state['host_captured']+=10
                    else:
                        if tx_source is not None:state['tx_buffer']|=value<<tx_bits
                        tx_bits+=10;tx_in+=10;tx_high=max(tx_high,tx_bits)
                    tx_quota-=1
                if host_block_words==8 and tx_slot%8==7:
                    # One collected beat, then two registered commit stages.
                    # Same-time converter reads precede commit. No CDC claim.
                    if len(state['host_blocks'])>=3:
                        fault='host_pipeline_overflow';break
                    state['host_blocks'].append((now+16/tx_hz,tuple(state['host_collect'])))
                    state['host_collect'].clear()
                    state['host_block_high']=max(state['host_block_high'],len(state['host_blocks']))
                tx_slot+=1
                if full_activity:
                    self.shared_rail.host_input(input_word)
                    if self.shared_rail.voltage<self.a.minimum_supply_v:
                        fault='shared_supply_low';break
            elif kind in (4,5) and host_cdc_read_hz is not None:
                fifo=state['host_cdc'];status=fifo.status()
                wr=abs((7+8*state['cdc_wr_index'])/tx_hz-now)<1e-18
                rd=abs((state['cdc_rd_index']+host_cdc_phase)/host_cdc_read_hz-now)<1e-18
                if self.shared_rail is not None:
                    self.shared_rail.block_clocks(wr,rd)
                    if self.shared_rail.voltage<self.a.minimum_supply_v:
                        fault='shared_supply_low';break
                pending=wr and state['host_blocks'] and state['host_blocks'][0][0]<=now+1e-18
                words=state['host_blocks'][0][1] if pending else None
                if words and not status['wr_ready']:
                    fault='host_cdc_full';break
                pop=bool(rd and status['rd_valid'] and tx_bits+10*len(status['words'])<=depth_bits)
                crossing=fifo.step(wr_edge=wr,rd_edge=rd,words=words or None,pop=pop)
                if pending:state['host_blocks'].popleft()
                if crossing['written']:
                    state['cdc_bits']+=10*len(words);state['cdc_written']+=10*len(words)
                if crossing['read'] is not None:
                    for value in crossing['read']:
                        if tx_source is not None:state['tx_buffer']|=value<<tx_bits
                        tx_bits+=10;tx_in+=10
                    bits=10*len(crossing['read'])
                    state['host_committed']+=bits;state['cdc_bits']-=bits
                    tx_high=max(tx_high,tx_bits)
                state['cdc_high']=max(state['cdc_high'],(fifo.wb-fifo.rb)%16)
                state['cdc_wr_index']+=int(wr);state['cdc_rd_index']+=int(rd)
            elif kind==4:
                _,words=state['host_blocks'][0]
                if tx_bits+10*len(words)>depth_bits:
                    fault='tx_overflow';break
                state['host_blocks'].popleft()
                for value in words:
                    if tx_source is not None:state['tx_buffer']|=value<<tx_bits
                    tx_bits+=10;tx_in+=10
                state['host_committed']+=10*len(words)
                tx_high=max(tx_high,tx_bits)
            else:
                _,captured,code,report_epoch=state['reports'].popleft()
                if report_epoch!=self.epoch:
                    fault='stale_feedback_epoch';break
                state['last_report']=(captured,code);state['reports_received']+=1
        if self.shared_rail is not None:self.shared_rail.advance(state['origin']+now)
        self.time=state['origin']+now
        state.update(frame=end_frame,occupancy=occupancy,produced=produced,returned=returned,
            high=high,sample_index=sample_index,rx_slot=rx_slot,tx_slot=tx_slot,
            rx_quota=quota,tx_quota=tx_quota,tx_bits=tx_bits,tx_min=tx_min,
            tx_high=tx_high,tx_in=tx_in,tx_out=tx_out)
        if host_block_words==8:
            assert state['host_captured']==state['host_committed']+state.get('cdc_bits',0)+10*(len(state['host_collect'])+sum(len(words) for _,words in state['host_blocks']))
        if host_cdc_read_hz is not None:
            fifo=state['host_cdc']
            assert state['cdc_bits']==sum(10*len(fifo.memory[(fifo.rb+i)%8]) for i in range((fifo.wb-fifo.rb)%16))
            assert state['cdc_written']==state['host_committed']+state['cdc_bits']
        assert produced == returned + occupancy
        assert (tx_prefill_bits if "tx" in directions else 0)+tx_in==tx_out+tx_bits
        if fault:
            self.state = 'fault'
            self.ready_at = math.inf
        staging={} if host_block_words==1 else dict(host_staging=dict(
            words_per_block=8,commit_beats=2,captured_bits=state['host_captured'],
            committed_bits=state['host_committed'],pending_bits=state['host_captured']-state['host_committed'],
            maximum_pending_blocks=state['host_block_high'],cdc_modeled=host_cdc_read_hz is not None))
        if host_cdc_read_hz is not None:
            staging['host_staging']['cdc']=dict(read_hz=host_cdc_read_hz,phase_cycles=host_cdc_phase,
                pending_bits=state['cdc_bits'],written_bits=state['cdc_written'],maximum_blocks=state['cdc_high'],
                write_edges=state['cdc_wr_index'],read_edges=state['cdc_rd_index'],
                scope='Ideal two-stage pointers and shared reset; no physical skew/metastability or clock-power claim')
        return dict(**staging,fault=fault, directions=list(directions),
                    feedback=dict(enabled=feedback,reports_received=state["reports_received"],
                        pending_reports=len(state["reports"]),header_argument_bits=8 if feedback else 0),
                    tx=dict(prefill_bits=tx_prefill_bits if 'tx' in directions else 0,
                        accepted_bits=tx_in,consumed_bits=tx_out,pending_bits=tx_bits,
                        minimum_bits=tx_min,maximum_bits=tx_high),
                    produced_bits=produced, returned_bits=returned,
                    pending_bits=occupancy, maximum_bits=high, depth_bits=depth_bits,
                    host_capacity_bps=rx_hz * plan.count(name) * 10 / len(plan),
                    h2d_capacity_bps=tx_hz * plan.count(name) * 10 / len(plan),
                    required_bps=rate * sample_bits, simulated_s=now)


def quality_budget(resources, a, *, bandwidth_hz=None, carrier_hz=None):
    if resources['engine'] == 'wire':
        ui = 1 / resources['line_rate_bps']
        # +/-7 sigma total opening screen. No assumed BER or normative mask.
        opening = 1 - a.wire_channel_closure_ui - a.wire_deterministic_jitter_ui - 14*a.wire_random_jitter_s/ui
        return dict(kind='timing_budget', residual_eye_ui=opening,
                    conditional_screen_pass=opening > 0,
                    omitted=['electrical amplitude/common mode', 'training/CDR transition density', 'protocol peer'])
    quantization = 10**(-(6.02*a.converter_enob+1.76-a.converter_backoff_db)/20)
    aperture = 2*math.pi*(bandwidth_hz/2)*a.sample_jitter_s
    evm = math.sqrt(quantization**2 + aperture**2 + a.relative_lo_phase_rms_rad**2 + a.frontend_evm_rms**2)
    return dict(kind='uncorrelated_error_budget', evm_rms=evm, quantization_evm=quantization,
                aperture_evm=aperture, carrier_hz=carrier_hz,
                illustrative_evm_limit=.10, conditional_screen_pass=evm <= .10,
                omitted=['filter equalization', 'blockers/spectral masks', 'packet acquisition', 'correlated impairments'])


def power_budget(resources, a, flow, contract, *, mode, dc_sink=False):
    """Average board/chip budget; no instantaneous pad or substrate simulation."""
    word_hz=(250e6 if mode==0 else 312.5e6)*a.host_clock_scale*a.d2h_clock_scale
    # CV charge per rising edge. Five data outputs per host segment; forwarded
    # clock lives in HOST_B and rises once per two DDR word edges.
    data_current=5*a.host_data_rising_probability*word_hz*a.host_output_cap_f*a.supply_v
    clock_current=.5*word_hz*a.host_output_cap_f*a.supply_v
    currents=dict(CORE=a.core_bias_a,PLL=a.pll_bias_a,
        HOST_A=a.host_segment_bias_a+data_current,
        HOST_B=a.host_segment_bias_a+data_current+clock_current,
        RF=0.,WIRE_A=0.,WIRE_B=0.)
    if resources['engine']=='rf':
        currents['RF']=a.rf_bias_a+(a.rf_output_power_w/(a.rf_efficiency*a.supply_v) if 'tx' in flow['directions'] else 0.)
    else:
        currents['WIRE_A']=a.wire_bias_a
    limits={d['id']:d['per_connection_budget_ma']/1000 for d in contract['power']['domains']}
    pin_limits={name:limits['HOST' if name.startswith('HOST') else 'WIRE' if name.startswith('WIRE') else name] for name in currents}
    external_return=.008 if dc_sink and 'tx' in flow['directions'] else 0.
    rx_termination=.008 if dc_sink and 'rx' in flow['directions'] else 0.
    # RX termination sources current through the pads to the external sink;
    # it is not counted again as a local on-die ground return.
    currents['WIRE_B']+=rx_termination
    ground_drop=a.return_resistance_ohm*(sum(currents.values())-rx_termination+external_return)
    rails={name:a.supply_v-a.feed_resistance_ohm*current-ground_drop for name,current in currents.items()}
    over=[name for name,current in currents.items() if current>pin_limits[name]]
    return dict(average_current_a=currents,per_connection_limits_a=pin_limits,
        estimated_rail_v=rails,over_budget_domains=over,
        local_supply_power_w=a.supply_v*sum(currents.values()),
        external_termination_power_w=external_return*3.3,
        local_rx_termination_power_w=rx_termination*a.supply_v,
        external_return_current_a=external_return,
        conditional_screen_pass=not over and min(rails.values())>=a.minimum_supply_v,
        scope='Provisional average bias, capacitive switching and DC droop; host drives continuous framed clock/data activity.',
        omitted=['edge current peaks','regulator dynamics','substrate coupling','thermal limits','wire rate-dependent current','TMDS termination transients'])


class EnvelopeFilter:
    """One-pole behavioral filter, exact ZOH endpoints and retained state."""
    def __init__(self, sample_hz, cutoff_hz):
        if min(sample_hz,cutoff_hz)<=0:raise ValueError('Positive filter rates required')
        self.decay=math.exp(-2*math.pi*cutoff_hz/sample_hz)
        self.rate=2*math.pi*cutoff_hz
        self.state=0j

    def step(self,value,interval):
        decay=math.exp(-self.rate*interval)
        self.state=decay*self.state+(1-decay)*value
        return self.state

    def process(self, values):
        values=np.asarray(values,complex)
        if not len(values):return values.copy()
        result,_=lfilter([1-self.decay],[1,-self.decay],values,zi=[self.decay*self.state])
        self.state=complex(result[-1])
        return result


class MultipoleEnvelope:
    """Persistent analog Butterworth modal states, exact ZOH endpoints."""
    def __init__(self,sample_hz,cutoff_hz,order):
        if type(order) is not int or not 1<=order<=5:raise ValueError('Filter order 1 through 5')
        if not all(math.isfinite(x) and x>0 for x in (sample_hz,cutoff_hz)):
            raise ValueError('Positive finite filter rates required')
        numerator,denominator=butter(order,1.,analog=True)
        self.weights,self.poles,direct=residue(numerator,denominator)
        assert not len(direct)
        self.decay=np.exp(self.poles*2*math.pi*cutoff_hz/sample_hz)
        self.rate=2*math.pi*cutoff_hz
        self.feed=(self.decay-1)/self.poles
        self.reset()

    def reset(self):
        self.state=np.zeros(len(self.poles),complex)

    def step(self,value,interval):
        decay=np.exp(self.poles*self.rate*interval)
        self.state=decay*self.state+np.expm1(self.poles*self.rate*interval)/self.poles*value
        return np.dot(self.weights,self.state)

    def process(self,values):
        values=np.asarray(values,complex)
        if values.ndim!=1 or not np.all(np.isfinite(values)):
            raise ValueError('Finite one-dimensional filter input required')
        if not len(values):return values.copy()
        result=np.zeros(len(values),complex)
        for index,(weight,decay,feed) in enumerate(zip(self.weights,self.decay,self.feed)):
            output,_=lfilter([feed],[1,-decay],values,zi=[decay*self.state[index]])
            self.state[index]=output[-1]
            result+=weight*output
        return result


class SampledRFStream:
    """Persistent sampled RF reduction with optional explicit sample timestamps."""
    def __init__(self,settings,*,offset_hz=0.,noise_rms=.001,seed=81,blocker_v=0.,blocker_hz=0.,saturation_v=None,ripple_v=0.,ripple_hz=1e6,lo_supply_hz_per_v=0.,clock_scale=1.,phase_rms_rad=0.,receive_source=None,external_substeps=0,frontend_noise_rms=0.,mixer_phase_source=None,tx_port_observer=None,tx_volts_per_unit=.5,tx_output_parameters=None):
        if receive_source is not None and not callable(receive_source):
            raise ValueError("Receive source must map physical times to complex envelopes")
        if type(external_substeps) is not int or not 0<=external_substeps<=64:
            raise ValueError('External quadrature subdivisions must be 0 through 64')
        if mixer_phase_source is not None and not callable(mixer_phase_source):
            raise ValueError('Mixer phase source must map timestamps to radians')
        if tx_port_observer is not None and (not callable(tx_port_observer) or not external_substeps):
            raise ValueError('TX port observation requires callable quadrature observer')
        if not math.isfinite(tx_volts_per_unit) or tx_volts_per_unit<=0:raise ValueError('Positive TX voltage scale required')
        self.tx_output_parameters=None
        if tx_output_parameters is not None:
            from tx_output_stage import output_envelope
            if tx_port_observer is None:raise ValueError('Output stage currently requires independent TX observation')
            if set(tx_output_parameters)!={'gain_imbalance_db','phase_error_deg','lo_feedthrough','cubic'}:
                raise ValueError('Declare every TX output parameter')
            output_envelope(0j,1+0j,**tx_output_parameters)
            self.tx_output_parameters=dict(tx_output_parameters)
        self.tx_port_observer=tx_port_observer;self.tx_volts_per_unit=tx_volts_per_unit
        self.mixer_phase_source=mixer_phase_source
        self.external_substeps=external_substeps
        self.receive_source=receive_source
        self.settings=validate_rf_settings(**settings)
        if not math.isfinite(clock_scale) or clock_scale<=0:raise ValueError('Positive finite converter clock scale required')
        self.actual_sample_hz=self.settings['sample_hz']*clock_scale
        if not math.isfinite(offset_hz) or not math.isfinite(noise_rms) or noise_rms<0:
            raise ValueError('Finite stream impairments required')
        if (not all(math.isfinite(v) for v in (blocker_v,blocker_hz,ripple_v,ripple_hz,lo_supply_hz_per_v))
                or blocker_v<0 or not 0<=ripple_v<3.3 or not 0<ripple_hz<self.actual_sample_hz/2
                or abs(blocker_hz)>=self.actual_sample_hz/2):
            raise ValueError('Invalid streaming impairment envelope')
        if saturation_v is not None and (not math.isfinite(saturation_v) or saturation_v<=0):
            raise ValueError('Positive saturation required')
        self.blocker_v=blocker_v;self.blocker_hz=blocker_hz;self.saturation_v=saturation_v
        self.ripple_v=ripple_v;self.ripple_hz=ripple_hz;self.lo_supply_hz_per_v=lo_supply_hz_per_v
        if not math.isfinite(phase_rms_rad) or phase_rms_rad<0:raise ValueError('Finite nonnegative phase noise required')
        self.phase_rms_rad=phase_rms_rad
        if not math.isfinite(frontend_noise_rms) or frontend_noise_rms<0:
            raise ValueError('Finite nonnegative frontend noise required')
        self.frontend_noise_rms=frontend_noise_rms
        self.offset_hz=offset_hz;self.noise_rms=noise_rms;self.seed=seed
        self.reset()

    def reset(self):
        s=self.settings
        self.tx_peak_open_v=0.
        self.tx=EnvelopeFilter(self.actual_sample_hz,s['tx_cutoff_hz'])
        self.rx=MultipoleEnvelope(self.actual_sample_hz,s['rx_cutoff_hz'],s['rx_filter_order'])
        self.previous_tx=0j;self.previous_received=0j;self.held_dac=0j;self.index=0
        self.rng=np.random.default_rng(self.seed)
        self.phase_rng=np.random.default_rng(self.seed+1009)
        self.frontend_rng=np.random.default_rng(self.seed+2027)
        self.dac_clips=0;self.adc_clips=0
        self.timed_mode=None;self.last_sample_time=None;self.analog_time=None;self.time_origin=None
        self.minimum_interval=math.inf;self.maximum_interval=0.

    def advance_analog_hold(self,end):
        """Evolve held-DAC and RF filters, without ADC/DAC edges or sample noise.

        Caller supplies bounded intervals and a valid continuous phase/source;
        this does not authorize clock recovery or approximate long gaps in one step.
        """
        if self.analog_time is None or not math.isfinite(end) or end<=self.analog_time:
            raise ValueError('Analog hold requires a later finite established epoch')
        return self.process([self.held_dac],sample_times_s=[end],_convert=False)

    @staticmethod
    def quantize(values,bits=12):
        step=2/(1<<bits)
        clips=int(np.count_nonzero((abs(values.real)>1)|(abs(values.imag)>1)))
        output=np.rint(np.clip(values.real,-1,1-step)/step)*step+1j*np.rint(np.clip(values.imag,-1,1-step)/step)*step
        return output,clips

    def process(self,values,*,supply_scale=1.,supply_phase_rad=0.,sample_times_s=None,_convert=True):
        if not _convert and (self.timed_mode is not True or not self.external_substeps):
            raise ValueError('Analog hold requires established timed quadrature state')
        if not math.isfinite(supply_scale) or supply_scale<=0 or not math.isfinite(supply_phase_rad):
            raise ValueError('Finite positive shared supply required')
        values=np.asarray(values,complex)
        if values.ndim!=1 or not np.all(np.isfinite(values)):
            raise ValueError('Finite one-dimensional converter samples required')
        if not len(values):return values.copy()
        timed=sample_times_s is not None
        if self.tx_port_observer is not None and not timed:raise ValueError('TX port requires absolute converter timestamps')
        if self.timed_mode is not None and timed!=self.timed_mode:
            raise ValueError('Cannot silently switch RF time coordinates')
        if timed:
            stamps=np.asarray(sample_times_s,float)
            if (stamps.shape!=values.shape or not np.all(np.isfinite(stamps)) or np.any(stamps<0)
                    or np.any(np.diff(stamps)<=0) or (self.analog_time is not None and stamps[0]<=self.analog_time)):
                raise ValueError('Strictly increasing finite converter timestamps required')
            previous=stamps[0]-1/self.actual_sample_hz if self.analog_time is None else self.analog_time
            intervals=np.diff(np.r_[previous,stamps])
            origin=float(stamps[0]) if self.time_origin is None else self.time_origin
            times=stamps-origin
        else:times=(self.index+np.arange(len(values)))/self.actual_sample_hz
        # Do not rebase an external source to the first local ADC edge.
        # Validate before committing clock, filter or random-generator state.
        incoming=None
        if self.receive_source is not None:
            incoming=np.asarray(self.receive_source(stamps.copy() if timed else times.copy()),complex)
            if incoming.shape!=values.shape or not np.all(np.isfinite(incoming)):
                raise ValueError('Receive source must return finite matching samples')
        mixer_phase=np.zeros(len(values))
        if self.mixer_phase_source is not None and not self.external_substeps:
            mixer_phase=np.asarray(self.mixer_phase_source(stamps.copy() if timed else times.copy()),float)
            if mixer_phase.shape!=values.shape or not np.all(np.isfinite(mixer_phase)):
                raise ValueError('Mixer phase source must return finite matching radians')
        subdrive=None
        if self.external_substeps:
            # Source and explicit mixer phase evolve at interval quadrature times.
            # The caller's separate shared-rail phase is still held per event.
            durations=intervals if timed else np.full(len(values),1/self.actual_sample_hz)
            absolute=stamps if timed else times
            fractions=(np.arange(self.external_substeps)+.5)/self.external_substeps
            subtimes=absolute[:,None]-durations[:,None]*(1-fractions)
            if self.receive_source is None or self.tx_port_observer is not None:
                if not timed:raise ValueError('Local TX quadrature requires explicit DAC edge timestamps')
                codes,_=self.quantize(values,self.settings['converter_bits'])
                held=np.r_[self.held_dac,codes[:-1]]
                state=self.tx.state;tx_endpoints=[state];tx_envelope=np.empty(subtimes.shape,complex)
                for k,(code,dt) in enumerate(zip(held,durations)):
                    tx_envelope[k]=code+(state-code)*np.exp(-self.tx.rate*dt*fractions)
                    state=code+(state-code)*math.exp(-self.tx.rate*dt)
                    tx_endpoints.append(state)
            if self.receive_source is None:
                subdrive=tx_envelope.copy()
            else:
                subdrive=np.asarray(self.receive_source(subtimes.ravel()),complex)
                if subdrive.shape!=(subtimes.size,) or not np.all(np.isfinite(subdrive)):
                    raise ValueError('Receive source must return finite quadrature samples')
                subdrive=subdrive.reshape(subtimes.shape)
            relative=subtimes-(origin if timed else 0.)
            subdrive=subdrive*np.exp(2j*math.pi*self.offset_hz*relative)+self.blocker_v*np.exp(2j*math.pi*self.blocker_hz*relative)
            subphase=self.lo_supply_hz_per_v*self.ripple_v/self.ripple_hz*(1-np.cos(2*math.pi*self.ripple_hz*relative))
            explicit_phase=0.
            if self.mixer_phase_source is not None:
                explicit_phase=np.asarray(self.mixer_phase_source(subtimes.ravel().copy()),float)
                if explicit_phase.shape!=(subtimes.size,) or not np.all(np.isfinite(explicit_phase)):
                    raise ValueError('Mixer phase source must return finite quadrature radians')
                explicit_phase=explicit_phase.reshape(subtimes.shape)
            if self.tx_port_observer is not None:
                # RX mixer phase is minus oscillator phase; the TX RF envelope
                # uses the opposite sign. RX gain/noise/filter never enter this tap.
                rotation=np.broadcast_to(np.exp(-1j*explicit_phase),tx_envelope.shape)
                if self.tx_output_parameters is None:port=tx_envelope*rotation
                else:
                    from tx_output_stage import output_envelope
                    port=output_envelope(tx_envelope,rotation,**self.tx_output_parameters)
                port=port*self.tx_volts_per_unit
                # The one-pole envelope follows a line segment in complex I/Q.
                # Affine imbalance/leakage preserves that property. Magnitude
                # is convex, and the validated cubic radial law is monotonic,
                # so its maximum is at one of the interval endpoints. LO phase
                # is unit magnitude and cannot change this bound.
                endpoints=np.asarray(tx_endpoints)
                if self.tx_output_parameters is not None:
                    endpoints=output_envelope(endpoints,np.ones(endpoints.shape),**self.tx_output_parameters)
                self.tx_peak_open_v=max(self.tx_peak_open_v,float(np.max(abs(endpoints)))*self.tx_volts_per_unit)
                self.tx_port_observer(subtimes.ravel().copy(),port.ravel().copy())
            subdrive*=np.exp(1j*(subphase+supply_phase_rad+explicit_phase))
            if self.saturation_v is not None:subdrive,_=compress_envelope(subdrive,self.saturation_v)
        if timed:
            self.time_origin=origin
            self.analog_time=float(stamps[-1])
            if _convert:
                edge_intervals=np.diff(np.r_[stamps[0]-1/self.actual_sample_hz if self.last_sample_time is None else self.last_sample_time,stamps])
                self.last_sample_time=float(stamps[-1])
                self.minimum_interval=min(self.minimum_interval,float(min(edge_intervals)))
                self.maximum_interval=max(self.maximum_interval,float(max(edge_intervals)))
        self.timed_mode=timed
        dac,clips=self.quantize(values,self.settings['converter_bits'])
        if _convert:self.dac_clips+=clips
        if timed:
            # DAC codes arrive at the stamped edge. The preceding interval uses
            # the previously latched code, including across chunk boundaries.
            held=np.r_[self.held_dac,dac[:-1]]
            tx=np.array([self.tx.step(value,dt) for value,dt in zip(held,intervals)])
        else:tx=self.tx.process(dac)
        self.held_dac=complex(dac[-1])
        drive=np.r_[self.previous_tx,tx[:-1]];self.previous_tx=complex(tx[-1])
        if incoming is not None:
            drive=np.r_[self.previous_received,incoming[:-1]]
            self.previous_received=complex(incoming[-1])
        if _convert:self.index+=len(values)
        drive=drive*np.exp(2j*math.pi*self.offset_hz*times)+self.blocker_v*np.exp(2j*math.pi*self.blocker_hz*times)
        ripple=self.ripple_v*np.sin(2*math.pi*self.ripple_hz*times)
        phase=self.lo_supply_hz_per_v*self.ripple_v/self.ripple_hz*(1-np.cos(2*math.pi*self.ripple_hz*times))
        drive*=np.exp(1j*(phase+supply_phase_rad+mixer_phase))
        if self.saturation_v is not None:drive,_=compress_envelope(drive,self.saturation_v)
        if subdrive is None:
            filtered=np.array([self.rx.step(value,dt) for value,dt in zip(drive,intervals)]) if timed else self.rx.process(drive)
        else:
            filtered=np.empty(len(values),complex)
            for k,(row,dt) in enumerate(zip(subdrive,durations)):
                for value in row:filtered[k]=self.rx.step(value,dt/self.external_substeps)
        if not _convert:return np.empty(0,complex)
        # Equivalent integrated frontend noise at the filter output, before
        # programmable gain. This is not an antenna-referred noise model.
        if self.frontend_noise_rms:
            front=self.frontend_rng.normal(size=(len(values),2))*self.frontend_noise_rms/math.sqrt(2)
            filtered=filtered+front[:,0]+1j*front[:,1]
        output=filtered*self.settings['rx_gain']*(1+ripple/3.3)*supply_scale
        if self.phase_rms_rad:
            output*=np.exp(1j*self.phase_rng.normal(0,self.phase_rms_rad,len(values)))
        # Draw paired quadratures per sample, independent of chunk boundaries.
        noise=self.rng.normal(size=(len(values),2))*self.noise_rms/math.sqrt(2)
        output+=noise[:,0]+1j*noise[:,1]
        adc,clips=self.quantize(output,self.settings['converter_bits']);self.adc_clips+=clips
        return adc


def rf_noise_placement_controls():
    """Check pre-gain versus post-gain noise and persistent random streams."""
    settings=dict(sample_hz=40e6,tx_cutoff_hz=20e6,rx_cutoff_hz=9e6,
                  rx_filter_order=5,converter_bits=12)
    separated=declared_rf_noise(.2,12)
    legacy=declared_rf_noise(.2,12,frontend_input_referred=False)
    assert math.isclose(separated['frontend_noise_rms']**2+separated['noise_rms']**2,
                        legacy['noise_rms']**2,rel_tol=1e-14)
    count=4096;zeros=np.zeros(count);seed=81;front=.008;post=.001
    pairs=[]
    for gain in (1.,2.):
        config=dict(settings,rx_gain=gain)
        def core():return SampledRFStream(config,seed=seed,frontend_noise_rms=front,noise_rms=post)
        whole=core();expected=whole.process(zeros)
        split=core();actual=np.r_[split.process(zeros[:73]),split.process(zeros[73:])]
        assert np.array_equal(expected,actual)
        f=np.random.default_rng(seed+2027).normal(size=(count,2))*front/math.sqrt(2)
        n=np.random.default_rng(seed).normal(size=(count,2))*post/math.sqrt(2)
        reference=gain*(f[:,0]+1j*f[:,1])+n[:,0]+1j*n[:,1]
        quantized,_=SampledRFStream.quantize(reference,12)
        assert np.array_equal(expected,quantized)
        pairs.append(dict(gain=gain,analytic_variance=gain**2*front**2+post**2,
                          observed_power=float(np.mean(abs(expected)**2))))
    return dict(status='passed',cases=pairs,chunk_exact=True,
                scope='Equivalent filter-output frontend noise before gain; converter noise after gain. No antenna noise figure or colored-noise qualification.')


def external_filter_convergence_controls():
    """Isolate external-input quadrature error against an analytic tone response.

    Refinement changes no bandwidth or impairment budget. This is a diagnostic,
    not a replacement external receive path or receiver qualification.
    """
    fs=40e6;cutoff=9.157407e6;order=5;count=512
    rows=[]
    for frequency in (173e3,5e6,9e6):
        # Independent polynomial transfer function, not the modal recurrence.
        numerator,denominator=butter(order,2*math.pi*cutoff,analog=True)
        transfer=np.polyval(numerator,2j*math.pi*frequency)/np.polyval(denominator,2j*math.pi*frequency)
        endpoints=np.arange(1,count+1)/fs
        expected=transfer*np.exp(2j*math.pi*frequency*endpoints)
        for convention in ('left','midpoint'):
            errors=[]
            for subdivisions in (1,2,4,8,16,32):
                filt=MultipoleEnvelope(fs,cutoff,order)
                dt=1/(fs*subdivisions)
                offset=0. if convention=='left' else .5
                times=(np.arange(count*subdivisions)+offset)*dt
                values=np.exp(2j*math.pi*frequency*times)
                observed=np.array([filt.step(v,dt) for v in values])[subdivisions-1::subdivisions]
                error=float(np.linalg.norm(observed[128:]-expected[128:])/np.linalg.norm(expected[128:]))
                errors.append(error)
            assert all(b<a for a,b in zip(errors,errors[1:]))
            assert errors[-1]<(.025 if convention=='left' else .001)
            rows.append(dict(frequency_hz=frequency,convention=convention,
                             subdivisions=[1,2,4,8,16,32],relative_complex_error=errors))
    return dict(status='passed',sample_hz=fs,cutoff_hz=cutoff,order=order,cases=rows,
                scope='Continuous-tone convergence only; not RF quality qualification')


def external_receive_controls():
    """Independent source timing, causal held drive and chunk-state checks."""
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,
                  rx_filter_order=5,converter_bits=12)
    stamps=13.37e-6+np.arange(512)/10e6
    stamps+=.3e-9*np.sin(np.arange(512)*.17)
    # Remote oscillator is a function of elapsed time, not the ADC index.
    def remote(t):return .2*np.exp(2j*np.pi*173e3*1.0001*(t-2.31e-6))
    def core(source=remote):return SampledRFStream(settings,receive_source=source,noise_rms=0.)
    whole=core();expected=whole.process(np.zeros(512),sample_times_s=stamps)
    split=core();actual=np.concatenate([
        split.process(np.full(73,.3),sample_times_s=stamps[:73]),
        split.process(np.full(439,-.2j),sample_times_s=stamps[73:])])
    assert np.array_equal(actual,expected)
    assert whole.previous_tx!=split.previous_tx
    # Independent replay of the causal RX filter using previous source values.
    rx=MultipoleEnvelope(10e6,1e6,5)
    intervals=np.diff(np.r_[stamps[0]-1/10e6,stamps])
    drive=np.r_[0j,remote(stamps[:-1])]
    oracle=np.array([rx.step(v,dt) for v,dt in zip(drive,intervals)])
    oracle,_=SampledRFStream.quantize(oracle,12)
    assert np.array_equal(oracle,expected)
    rebased=core(lambda t:remote(t-stamps[0]))
    assert not np.array_equal(rebased.process(np.zeros(512),sample_times_s=stamps),expected)
    invalid=core(lambda t:np.full(len(t),np.nan))
    try:invalid.process(np.zeros(512),sample_times_s=stamps)
    except ValueError:pass
    else:raise AssertionError('Invalid external source accepted')
    assert invalid.index==0 and invalid.last_sample_time is None and invalid.timed_mode is None
    invalid.receive_source=remote
    assert np.array_equal(invalid.process(np.zeros(512),sample_times_s=stamps),expected)
    for subdivisions in (1,4,16):
        def refined():return SampledRFStream(settings,receive_source=remote,external_substeps=subdivisions)
        whole=refined();split=refined()
        expected=whole.process(np.zeros(512),sample_times_s=stamps)
        actual=np.r_[split.process(np.zeros(73),sample_times_s=stamps[:73]),
                     split.process(np.zeros(439),sample_times_s=stamps[73:])]
        assert np.array_equal(actual,expected)
    return dict(status='passed',samples=512,refined_chunk_exact=True,chunk_exact=True,local_tx_independent=True,
                absolute_source_time=True,causal_held_drive=True,
                scope='Normalized external envelope; no antenna-port or protocol qualification')


def multipole_envelope(values,sample_hz,cutoff_hz,order):
    """Zero-state convenience call; stream owners retain MultipoleEnvelope."""
    return MultipoleEnvelope(sample_hz,cutoff_hz,order).process(values)


def acquire_training(samples, sample_hz, known, maximum_delay_samples=8):
    """FPGA observer fits delay and scalar gain from a separate known prefix.

    Search uses an explicit bounded delay budget. Payload samples/labels are not
    arguments. No frequency-selective equalization or carrier recovery is implied.
    """
    if not math.isfinite(maximum_delay_samples) or not 0<maximum_delay_samples<=64:
        raise ValueError('Training delay budget must be within 64 converter periods')
    indices=np.arange(16,len(known)-16-math.ceil(maximum_delay_samples))
    reference=known[indices]
    timeline=np.arange(len(samples))+1
    best=None
    for delay in np.linspace(0,maximum_delay_samples,math.ceil(maximum_delay_samples*8)+1):
        at=indices+delay
        observed=np.interp(at,timeline,samples.real)+1j*np.interp(at,timeline,samples.imag)
        gain=np.vdot(reference,observed)/np.vdot(reference,reference)
        error=float(np.mean(abs(observed-gain*reference)**2)/max(1e-30,np.mean(abs(observed)**2)))
        if best is None or error<best[0]:best=(error,delay,gain)
    error,delay,gain=best
    if abs(gain)<.05 or error>.1 or delay>=maximum_delay_samples:
        return dict(acquired=False,residual=error,delay_s=delay/sample_hz,gain=complex(gain))
    return dict(acquired=True,residual=error,delay_s=delay/sample_hz,gain=complex(gain))


def pilot_phase_correct(data, pilots):
    """Per-symbol common phase from normalized +1 diagnostic pilots only."""
    data=np.asarray(data,complex);pilots=np.asarray(pilots,complex)
    if data.ndim!=2 or pilots.ndim!=2 or len(data)!=len(pilots) or not pilots.shape[1]:
        raise ValueError('Matching data and pilot blocks required')
    if not np.all(np.isfinite(data)) or not np.all(np.isfinite(pilots)):
        raise ValueError('Finite pilot observations required')
    energy=np.mean(abs(pilots)**2,axis=1)
    vector=np.mean(pilots,axis=1)
    coherence=abs(vector)**2/np.maximum(energy,1e-30)
    if np.any(energy<1e-12) or np.any(coherence<.5):
        raise ValueError('Missing or incoherent pilots')
    phase=np.angle(vector)
    return data*np.exp(-1j*phase[:,None]),phase

def windowed_sinc_samples(values,coordinates,radius=8):
    """Finite external-receiver interpolator; no extension beyond capture."""
    values=np.asarray(values,complex);coordinates=np.asarray(coordinates,float)
    if (values.ndim!=1 or coordinates.ndim!=1 or type(radius) is not int or radius<2
            or not np.all(np.isfinite(values)) or not np.all(np.isfinite(coordinates))):
        raise ValueError('Finite capture, coordinates and integer interpolation radius required')
    indices=np.floor(coordinates).astype(int)[:,None]+np.arange(1-radius,radius+1)
    if indices.size and (indices.min()<0 or indices.max()>=len(values)):
        raise ValueError('Interpolation support outside capture')
    delta=coordinates[:,None]-indices
    weights=np.sinc(delta)*np.sinc(delta/radius)
    weights/=weights.sum(axis=1,keepdims=True)
    return np.sum(values[indices]*weights,axis=1)

def training_clock_rate(known,received,fft_size,cp,bins):
    """Estimate constant sample-rate error from known training, not payload."""
    bins=np.asarray(bins,int);bins=bins[abs(bins)<=80]
    transform=TrainedBlockEqualizer(fft_size,cp,bins%fft_size)
    x=transform.spectrum(known);y=transform.spectrum(received)
    if x.shape!=y.shape or len(x)<3 or np.any(abs(x)<1e-9) or np.any(abs(y)<1e-9):
        raise ValueError('Observable matching training blocks required')
    channel=y/x;relative=channel*channel[0].conj()
    phase=np.unwrap(np.angle(relative),axis=1)
    design=np.column_stack((np.ones(len(bins)),bins))
    slopes=np.linalg.lstsq(design,phase.T,rcond=None)[0][1]
    rate=np.polyfit(np.arange(len(slopes)),slopes,1)[0]*fft_size/(2*np.pi*(fft_size+cp))
    if not math.isfinite(rate) or abs(rate)>500e-6:
        raise ValueError('Training rate estimate outside candidate envelope')
    return dict(rate_error_ppm=float(rate*1e6),training_blocks=len(x),maximum_fitted_bin=80)

def pilot_timing_correct(data,pilots,data_bins,pilot_bins):
    """External receiver: affine subcarrier phase from known +1 pilots only."""
    data=np.asarray(data,complex);pilots=np.asarray(pilots,complex)
    data_bins=np.asarray(data_bins,float);pilot_bins=np.asarray(pilot_bins,float)
    if (data.ndim!=2 or pilots.ndim!=2 or len(data)!=len(pilots)
            or data.shape[1]!=len(data_bins) or pilots.shape[1]!=len(pilot_bins)
            or len(pilot_bins)<3 or np.any(np.diff(pilot_bins)<=0)):
        raise ValueError('Ordered pilot bins and matching blocks required')
    if not all(np.all(np.isfinite(x)) for x in (data,pilots,data_bins,pilot_bins)) or np.any(abs(pilots)<1e-6):
        raise ValueError('Missing or nonfinite pilot observations')
    design=np.column_stack((np.ones(len(pilot_bins)),pilot_bins))
    fit=np.linalg.lstsq(design,np.unwrap(np.angle(pilots),axis=1).T,rcond=None)[0].T
    phase=fit[:,0,None]+fit[:,1,None]*data_bins
    pilot_phase=fit[:,0,None]+fit[:,1,None]*pilot_bins
    return data*np.exp(-1j*phase),pilots*np.exp(-1j*pilot_phase),fit

def crossfit_constellation_phase(observed,bins,constellation):
    """External receiver affine phase fit on disjoint alternating tone sets.

    Hard decisions use fixed modulation points, not transmitted labels. Each
    output tone uses a fit that excludes that tone. Wrong codewords remain an
    external integrity concern; this is not an acquisition or quality gate.
    """
    values=np.asarray(observed,complex);bins=np.asarray(bins,float)
    points=np.asarray(constellation,complex)
    if (values.ndim!=2 or not values.size or bins.shape!=(values.shape[1],)
            or len(bins)<6 or len(np.unique(bins))!=len(bins)
            or points.ndim!=1 or not len(points)
            or not all(np.all(np.isfinite(x)) for x in (values,bins,points))
            or np.any(abs(values)<1e-12) or np.any(abs(points)<1e-12)):
        raise ValueError('Observable tone blocks, distinct bins and nonzero constellation required')
    output=values.copy();fits=[]
    for parity in (0,1):
        selected=np.arange(len(bins))%2==parity;held=~selected
        source=values[:,selected]
        nearest=points[np.argmin(abs(source[...,None]-points),axis=-1)]
        residual=np.angle(source*nearest.conj())
        design=np.column_stack((np.ones(sum(selected)),bins[selected]))
        fit=np.linalg.lstsq(design,residual.T,rcond=None)[0].T
        output[:,held]*=np.exp(-1j*(fit[:,0,None]+fit[:,1,None]*bins[held]))
        fits.append(fit)
    return output,np.asarray(fits)


def receiver_estimation_controls():
    bins=np.arange(-32,32)
    bits=np.random.default_rng(1).choice([-1.,1.],(4,64))
    received=bits*np.exp(1j*(.07+.001*bins))
    corrected,fit=crossfit_constellation_phase(received,bins,[-1.,1.])
    assert np.max(abs(corrected-bits))<1e-12
    changed=received.copy();changed[:,1::2]*=np.exp(.05j)
    _,other=crossfit_constellation_phase(changed,bins,[-1.,1.])
    assert np.array_equal(fit[0],other[0])
    for bad in (np.zeros_like(received),np.full_like(received,np.nan)):
        try:crossfit_constellation_phase(bad,bins,[-1.,1.])
        except ValueError:pass
        else:raise AssertionError('Unobservable phase input admitted')
    wave=fixture('wifi_he20',seed=1907);cp=wave.metadata['cp'];delays=np.arange(-4,12)
    eq=TrainedBlockEqualizer(256,cp,np.asarray(wave.metadata['data'])%256,channel_delays=delays)
    taps=np.zeros(16,complex);taps[4]=1;taps[5]=.12j;taps[7]=.05
    spectrum=np.fft.fft(wave.samples.reshape(-1,256+cp)[:,cp:],axis=1)
    response=np.exp(-2j*np.pi*np.arange(256)[:,None]*delays/256)@taps
    blocks=np.fft.ifft(spectrum*response,axis=1)
    received=np.concatenate([np.r_[v[-cp:],v] for v in blocks])
    eq.train(wave.samples,received)
    assert np.max(abs(eq.response-response[eq.bins]))<1e-12
    try:eq.train(wave.samples,np.zeros_like(received))
    except ValueError:pass
    else:raise AssertionError('Silent training admitted')
    assert eq.response is None
    return dict(status='passed',known_channel_recovered=True,held_tones_excluded_from_phase_fit=True,
                silent_retraining_invalidates=True,
                scope='External receiver mechanics only; no full RF or wrong-decision qualification')


def constellation_quality(observed,constellation,limit=.1):
    """External modem residual against fixed allowed points, without labels.

    A wrong valid codeword can pass. This supplements, never replaces, external
    integrity checks and does not fit gain, phase or transmitted payload.
    """
    values=np.asarray(observed,complex);points=np.asarray(constellation,complex)
    if (not values.size or points.ndim!=1 or not points.size
            or not np.all(np.isfinite(values)) or not np.all(np.isfinite(points))
            or not math.isfinite(limit) or limit<=0):
        raise ValueError('Finite observations, constellation and positive limit required')
    nearest=points[np.argmin(abs(values[...,None]-points),axis=-1)]
    energy=float(np.vdot(nearest,nearest).real)
    if energy<=1e-30:raise ValueError('Constellation decisions have no reference energy')
    evm=float(np.linalg.norm(values-nearest)/math.sqrt(energy))
    return dict(evm_rms=evm,limit=limit,accepts=evm<=limit,
                scope='Decision residual only; wrong valid codewords require external integrity checks')


def known_pilot_quality(observed,known,limit=.1):
    """Receiver-visible residual; no unknown data tones or payload labels."""
    observed=np.asarray(observed,complex);known=np.asarray(known,complex)
    if observed.ndim!=2 or not observed.size or known.shape!=(observed.shape[1],):
        raise ValueError('Complete pilot blocks and matching known tones required')
    if not np.all(np.isfinite(observed)) or not np.all(np.isfinite(known)) or not math.isfinite(limit) or limit<=0:
        raise ValueError('Finite pilots and positive quality limit required')
    energy=float(np.vdot(known,known).real)
    if energy<1e-12:raise ValueError('Known pilots have no energy')
    per_block=np.sqrt(np.sum(abs(observed-known)**2,axis=1)/energy)
    evm=float(np.sqrt(np.mean(per_block**2)))
    return dict(evm_rms=evm,per_block_evm_rms=per_block.tolist(),limit=limit,
        accepts=evm<=limit,scope='Pilot-only proxy; not a guarantee for unobserved data tones')



def compress_envelope(values, saturation_v):
    """Smooth memoryless complex-envelope limiter; unity small-signal gain.

    Saturation is in the modeled internal envelope coordinate, not antenna dBm.
    No AM/PM, device memory or physical IIP3 claim is implied.
    """
    if not math.isfinite(saturation_v) or saturation_v<=0:
        raise ValueError('Positive finite envelope saturation required')
    values=np.asarray(values,complex)
    gain=1/np.sqrt(1+(abs(values)/saturation_v)**2)
    return values*gain,gain


def bandlimited_samples(values, positions, half_width=32, cutoff=1.):
    """Finite windowed-sinc reconstruction, with zero extension at boundaries.

    Positions are in input-sample units. This centered analysis operation needs
    half_width input samples of lookahead. Callers must explicitly account for
    that latency/storage when claiming an FPGA implementation. It is not an
    on-chip resampler or a free causal interpolation primitive.
    """
    values=np.asarray(values,complex);positions=np.asarray(positions,float)
    if (values.ndim!=1 or not len(values) or positions.ndim!=1 or not np.all(np.isfinite(values))
            or not np.all(np.isfinite(positions)) or type(half_width) is not int
            or half_width<2 or not 0<cutoff<=1):
        raise ValueError('Finite resampling inputs and bounded FIR required')
    offsets=np.arange(-half_width+1,half_width+1)
    result=np.empty(len(positions),complex)
    # Bound temporary analysis storage independently of waveform duration.
    for start in range(0,len(positions),1024):
        p=positions[start:start+1024]
        indices=np.floor(p).astype(np.int64)[:,None]+offsets
        delta=p[:,None]-indices
        weights=cutoff*np.sinc(cutoff*delta)*np.where(abs(delta)<half_width,
            .5+.5*np.cos(np.pi*delta/half_width),0.)
        weights/=weights.sum(axis=1)[:,None]
        valid=(indices>=0)&(indices<len(values))
        result[start:start+len(p)]=np.sum(weights*np.where(valid,
            values[np.clip(indices,0,len(values)-1)],0j),axis=1)
    return result


def waveform_screen(wave, a, power, *, seed=81, settings=None, carrier_offset_hz=0., recover_carrier=False, blocker=None, rx_order=None, frontend_saturation_v=None, supply_ripple=None, fpga_resampling=False, mixer_phase_noise=None, sample_phase_noise=None, mixer_substeps=1, frontend_loss_db=0., pga_peak_limit_v=None, training_samples=512):
    """Seeded sampled-envelope screen; no RF carrier or analog ODE integration.

    Selectable conversion, ZOH source contract, causal one-pole TX/RX
    filter hypotheses. Separate known prefix drives FPGA delay/gain acquisition.
    """
    if type(training_samples) is not int or not 512<=training_samples<=4096 or training_samples%64:
        raise ValueError('Diagnostic prefix requires 512–4096 samples in multiples of 64')
    if not math.isfinite(carrier_offset_hz):raise ValueError('Finite carrier offset required')
    if type(fpga_resampling) is not bool:raise ValueError('Boolean FPGA resampling selection required')
    if type(mixer_substeps) is not int or mixer_substeps not in (1,2,4,8):
        raise ValueError('Bounded mixer refinement required')
    if not math.isfinite(frontend_loss_db) or frontend_loss_db<0:
        raise ValueError('Finite nonnegative frontend insertion loss required')
    if pga_peak_limit_v is not None and (not math.isfinite(pga_peak_limit_v) or pga_peak_limit_v<=0):
        raise ValueError('Positive finite PGA peak headroom required')
    if wave.kind=='lora' and wave.metadata.get('oversample',1)==1:
        wave=lora(wave.symbols,sf=wave.metadata['sf'],bandwidth=wave.metadata['bandwidth'],oversample=8)
    settings=validate_rf_settings(**(settings or {}))
    if rx_order is None:rx_order=settings['rx_filter_order']
    rng=np.random.default_rng(seed)
    rms=float(np.sqrt(np.mean(abs(wave.samples)**2)))
    amplitude=10**(-a.converter_backoff_db/20)
    x=wave.samples*(amplitude/rms)
    block_training=None
    payload_x=x.copy()
    if wave.kind=='he20':
        block_training=fixture('wifi_he20',seed=1907).samples*(amplitude/rms)
        x=np.r_[block_training,x]
    step=2/(1<<settings['converter_bits'])
    def quantize(z):
        clipped=int(np.count_nonzero((abs(z.real)>1)|(abs(z.imag)>1)))
        return (np.rint(np.clip(z.real,-1,1-step)/step)*step+
                1j*np.rint(np.clip(z.imag,-1,1-step)/step)*step),clipped
    converter_hz=settings['sample_hz']
    if mixer_phase_noise is not None:
        if a.relative_lo_phase_rms_rad!=0:
            raise ValueError('Select spectral mixer phase or legacy IID phase, not both')
        if mixer_phase_noise.maximum_offset_hz>=converter_hz/2:
            raise ValueError('Mixer noise needs a resolved offset band below converter Nyquist')
    if sample_phase_noise is not None:
        if settings.get('sample_clock_source')!='external_lo':
            raise ValueError('Shared LO sample error requires the explicit direct-LO divider')
        if sample_phase_noise.maximum_offset_hz>=converter_hz/2:
            raise ValueError('Sample phase noise exceeds the resolved offset band')
    payload_count=math.ceil(len(x)/wave.sample_hz*converter_hz)
    count=payload_count
    ratio=Fraction(str(wave.sample_hz))/Fraction(str(converter_hz))
    indices=np.fromiter((i*ratio.numerator//ratio.denominator for i in range(count)),dtype=np.int64,count=count)
    source=x[np.minimum(indices,len(x)-1)]
    resampler=None
    if fpga_resampling:
        # FPGA can precompute TX samples, but cannot consume future samples
        # without latency. Delay the modeled DAC sequence by 32 source samples.
        half_width=32
        delay_s=half_width/wave.sample_hz
        count=math.ceil((len(x)+2*half_width)/wave.sample_hz*converter_hz)
        positions=np.arange(count)*wave.sample_hz/converter_hz-half_width
        source=bandlimited_samples(x,positions,half_width,
            cutoff=min(1.,converter_hz/wave.sample_hz))
        resampler=dict(owner='external_fpga',taps=2*half_width,
            tx_latency_s=delay_s,rx_lookahead_s=half_width/converter_hz,
            history_complex_samples_per_direction=2*half_width,
            coefficients='ideal calculated coefficients; FPGA quantization/throughput unqualified',
            on_chip_resampler=False)
    repetition=32 if converter_hz<10e6 else 64
    training_rng=np.random.default_rng(912)
    training=amplitude*np.repeat(np.exp(1j*(np.pi/4+np.pi/2*training_rng.integers(0,4,repetition//4))),4)
    training=np.tile(training,training_samples//repetition)
    # Band-limit the diagnostic prefix to the selected receive bandwidth.
    # This uses declared settings only, never unknown payload values.
    training=EnvelopeFilter(converter_hz,settings['rx_cutoff_hz']/4).process(training)
    training*=amplitude/np.sqrt(np.mean(abs(training)**2))
    prefix=len(training)+16
    source=np.r_[training,np.zeros(16),source,np.zeros(16)]
    count=len(source)
    dac,dac_clipped=quantize(source)
    tx=EnvelopeFilter(converter_hz,settings['tx_cutoff_hz']).process(dac)
    # RX sees the previous TX endpoint: no future sample enters the filter.
    mixer_hz=converter_hz*mixer_substeps
    mixer_count=count*mixer_substeps
    mixer_times=np.arange(mixer_count)/mixer_hz
    mixer_input=np.repeat(np.r_[0j,tx[:-1]],mixer_substeps)*np.exp(2j*math.pi*carrier_offset_hz*mixer_times)
    if blocker is not None:
        offset=blocker['offset_hz'];level=blocker['relative_power_db']
        if not math.isfinite(offset) or not math.isfinite(level) or abs(offset)>=converter_hz/2:
            raise ValueError('Finite blocker strictly inside converter Nyquist interval required')
        mixer_input+=amplitude*10**(level/20)*np.exp(2j*math.pi*offset*mixer_times)
    mixer_input*=10**(-frontend_loss_db/20)
    mixer_phase=None
    if mixer_phase_noise is not None:
        mixer_phase=mixer_phase_noise.phase(mixer_times)
        # Receive downconversion multiplies BOTH wanted signal and blockers by
        # conjugate LO phase, before analog filtering: reciprocal mixing remains.
        mixer_input*=np.exp(-1j*mixer_phase)
    ripple_v=np.zeros(mixer_count)
    ripple_phase=np.zeros(mixer_count)
    if supply_ripple is not None:
        amplitude_v=supply_ripple['amplitude_v'];frequency=supply_ripple['frequency_hz']
        sensitivity=supply_ripple['lo_sensitivity_hz_per_v']
        if (not all(math.isfinite(v) for v in (amplitude_v,frequency,sensitivity)) or
                not 0<=amplitude_v<power['estimated_rail_v']['RF'] or
                not 0<frequency<converter_hz/2):
            raise ValueError('Invalid supply ripple envelope')
        ripple_time=mixer_times
        ripple_v=amplitude_v*np.sin(2*math.pi*frequency*ripple_time)
        # Integral of 2*pi*K*A*sin(2*pi*f*t), with zero initial phase.
        ripple_phase=sensitivity*amplitude_v/frequency*(1-np.cos(2*math.pi*frequency*ripple_time))
        mixer_input*=np.exp(1j*ripple_phase)
    compression=None
    if frontend_saturation_v is not None:
        mixer_input,frontend_gain=compress_envelope(mixer_input,frontend_saturation_v)
        compression=dict(saturation_v=frontend_saturation_v,
            minimum_gain=float(frontend_gain.min()),mean_gain=float(frontend_gain.mean()),
            samples_beyond_1db=int(np.count_nonzero(frontend_gain<10**(-1/20))))
    filtered=multipole_envelope(mixer_input,mixer_hz,settings['rx_cutoff_hz'],rx_order)
    filter_times=(np.arange(mixer_count)+1)/mixer_hz
    times=(np.arange(count)+1)/converter_hz
    jitter=rng.normal(0,a.sample_jitter_s,count)
    shared_jitter=np.zeros(count)
    if sample_phase_noise is not None:
        # First-order solution of omega*t+phi(t)=2*pi*n*divider. Ideal division
        # does not reduce source absolute timing error. Independent aperture
        # error is the separately declared sample_jitter_s above.
        shared_jitter=-sample_phase_noise.phase(times)/(2*math.pi*settings['lo_hz'])
        jitter+=shared_jitter
    if np.any(np.diff(times+jitter)<=0):raise ValueError('Nonmonotonic converter sample times')
    sampled=(np.interp(times+jitter,np.r_[0.,filter_times],np.r_[0.,filtered.real])+
             1j*np.interp(times+jitter,np.r_[0.,filter_times],np.r_[0.,filtered.imag]))
    ripple_v=np.interp(times,np.r_[0.,filter_times],np.r_[0.,ripple_v])
    phase=rng.normal(0,a.relative_lo_phase_rms_rad,count)
    gain=power['estimated_rail_v']['RF']/a.supply_v*settings['rx_gain']
    z=(gain+settings['rx_gain']*ripple_v/a.supply_v)*sampled*np.exp(1j*phase)
    pga_peak=float(max(np.max(abs(z.real)),np.max(abs(z.imag))))
    pga_slew=float(max(np.max(abs(np.diff(z.real))),np.max(abs(np.diff(z.imag))))*converter_hz)
    pga_clipped=0
    if pga_peak_limit_v is not None:
        pga_clipped=int(np.count_nonzero((abs(z.real)>pga_peak_limit_v)|(abs(z.imag)>pga_peak_limit_v)))
        z=np.clip(z.real,-pga_peak_limit_v,pga_peak_limit_v)+1j*np.clip(z.imag,-pga_peak_limit_v,pga_peak_limit_v)
    frontend_sigma=amplitude*a.frontend_evm_rms/math.sqrt(2)
    # ENOB is represented by input-referred white noise beyond ideal 12-bit ADC.
    adc_sigma=math.sqrt(max(0.,(2**(1-a.converter_enob))**2-step**2)/12)
    # Frontend equivalent noise precedes programmable/supply gain; ADC ENOB
    # noise follows it. Sum independent variances at the converter input.
    sigma=np.hypot(frontend_sigma*(gain+settings['rx_gain']*ripple_v/a.supply_v),adc_sigma)
    z+=sigma*(rng.normal(size=count)+1j*rng.normal(size=count))
    received,adc_clipped=quantize(z)
    carrier=dict(enabled=recover_carrier,acquired=False,estimate_hz=None,
                 capture_limit_hz=converter_hz/(2*repetition),repetition_samples=repetition)
    if recover_carrier:
        try:
            estimate,coherence=repeated_training_frequency(received[256:256+2*repetition],repetition,converter_hz)
            # Refine over the settled known repeats using phase progression; coarse
            # derotation keeps the phase slope unambiguous within capture range.
            blocks=received[64:training_samples].reshape(-1,repetition)
            correlations=blocks@blocks[0].conj()
            elapsed=np.arange(len(blocks))*repetition/converter_hz
            residual_phase=np.unwrap(np.angle(correlations*np.exp(-2j*math.pi*estimate*elapsed)))
            estimate+=float(np.polyfit(elapsed,residual_phase,1)[0]/(2*math.pi))
            received*=np.exp(-2j*math.pi*estimate*times)
            carrier.update(acquired=True,estimate_hz=estimate,coherence=coherence)
        except ValueError as error:carrier['reason']=str(error)
    delay_budget=min(64.,max(8.,math.ceil(2+rx_order*converter_hz/(math.pi*settings['rx_cutoff_hz']))))
    acquisition=acquire_training(received[:len(training)],converter_hz,training,delay_budget)
    acquisition['search_limit_samples']=delay_budget
    observer_times=prefix/converter_hz+np.arange(len(x))/wave.sample_hz
    if resampler is not None:observer_times+=resampler['tx_latency_s']
    raw=(np.interp(observer_times,times,received.real)+1j*np.interp(observer_times,times,received.imag))
    raw_evm=float(np.sqrt(np.mean(abs(raw-x)**2)/np.mean(abs(x)**2)))
    if acquisition['acquired']:observer_times+=acquisition['delay_s']
    converter_received=received
    received=(np.interp(observer_times,np.r_[0.,times],np.r_[0.,received.real])+
              1j*np.interp(observer_times,np.r_[0.,times],np.r_[0.,received.imag]))
    if resampler is not None:
        # Index zero of received is at 1/converter_hz. The observer is in the
        # external FPGA and needs the declared lookahead before releasing data.
        received=bandlimited_samples(converter_received,
            observer_times*converter_hz-1,half_width,
            cutoff=min(1.,wave.sample_hz/converter_hz))
    if acquisition['acquired']:received/=acquisition['gain']
    acquisition['gain_real']=acquisition['gain'].real
    acquisition['gain_imag']=acquisition['gain'].imag
    del acquisition['gain']
    equalized=None
    if block_training is not None:
        training_rx=received[:len(block_training)]
        received=received[len(block_training):]
        raw=raw[len(block_training):]
        x=payload_x
        eq=TrainedBlockEqualizer(256,wave.metadata['cp'],np.asarray(wave.metadata['data'])%256)
        try:
            eq.train(block_training,training_rx)
            observed=eq.observe(received)
            expected=eq.spectrum(payload_x)
            untracked_evm=float(np.linalg.norm(observed-expected)/np.linalg.norm(expected))
            pilot_eq=TrainedBlockEqualizer(256,wave.metadata['cp'],np.asarray(wave.metadata['pilots'])%256)
            pilot_eq.train(block_training,training_rx)
            pilot_observed=pilot_eq.observe(received)
            observed,pilot_phase=pilot_phase_correct(observed,pilot_observed)
            equalized=dict(acquired=True,pilot_tracking=True,untracked_evm_rms=untracked_evm,pilot_phase_rad=pilot_phase.tolist(),evm_rms=float(np.linalg.norm(observed-expected)/np.linalg.norm(expected)),
                symbol_errors=int(np.count_nonzero((observed.real>0).ravel()!=wave.symbols)),
                training_symbols=len(block_training)//(256+wave.metadata['cp']),
                minimum_channel_gain=float(np.min(abs(eq.response))))
        except ValueError as error:
            equalized=dict(acquired=False,reason=str(error))
    decoded=decisions(wave,received*rms/amplitude)
    errors=int(np.count_nonzero(decoded!=wave.symbols))
    evm=float(np.sqrt(np.mean(abs(received-x)**2)/np.mean(abs(x)**2)))
    quality_evm=equalized['evm_rms'] if equalized and equalized['acquired'] else evm
    quality_errors=equalized['symbol_errors'] if equalized and equalized['acquired'] else errors
    return dict(symbols=len(wave.symbols),symbol_errors=errors,evm_rms=evm,equalized=equalized,
        dac_clipped_samples=dac_clipped,adc_clipped_samples=adc_clipped,
        pga_headroom=dict(frontend_loss_db=frontend_loss_db,configured_gain=settings['rx_gain'],signal_peak_per_component_v=pga_peak,peak_limit_v=pga_peak_limit_v,clipped_signal_samples=pga_clipped,sampled_slew_lower_bound_v_per_s=pga_slew,scope='Signal headroom before injected noise; sampled slew is a lower bound, not continuous-time drive qualification.'),
        converter_hz=converter_hz,mixer_substeps=mixer_substeps,rx_filter_order=rx_order,supply_ripple=supply_ripple,peak_supply_phase_rad=float(np.max(abs(ripple_phase))),blocker=blocker,frontend_compression=compression,carrier_offset_hz=carrier_offset_hz,carrier_recovery=carrier,dac_updates=count,adc_samples=count,
        spectral_clock=None if mixer_phase_noise is None else dict(injection='receive_mixer_before_filter',realization_line_phase_variance_rad2=mixer_phase_noise.variance_rad2,realized_phase_rms_rad=float(np.sqrt(np.mean(mixer_phase**2))),shared_sample_time_error_rms_s=float(np.sqrt(np.mean(shared_jitter**2))),sample_time_model='first-order LO phase crossing plus independent aperture error; stimulus DAC remains independently timed',maximum_offset_hz=mixer_phase_noise.maximum_offset_hz),
        tx_filter_cutoff_hz=settings['tx_cutoff_hz'],rx_filter_cutoff_hz=settings['rx_cutoff_hz'],rx_gain=settings['rx_gain'],
        timing_recovery=acquisition,unaligned_evm_rms=raw_evm,fixture_samples=len(x),fixture_sample_hz=wave.sample_hz,duration_s=wave.duration,training_samples=training_samples,training_and_guard_s=(training_samples+32)/converter_hz+(len(block_training)/wave.sample_hz if block_training is not None else 0)+(2*resampler['tx_latency_s'] if resampler else 0),fpga_resampler=resampler,
        raw_received_rms_v=float(np.sqrt(np.mean(abs(raw)**2))),received_rms_v=float(np.sqrt(np.mean(abs(received)**2))),rf_rail_gain=gain,seed=seed,conditional_screen_pass=(not recover_carrier or carrier['acquired']) and acquisition['acquired'] and (equalized is None or equalized['acquired']) and quality_evm<=.10 and quality_errors==0 and pga_clipped==0,
        scope='Selectable-rate ZOH conversion, causal one-pole TX/RX hypotheses, ENOB/noise/phase/jitter and rail gain; independent known-prefix delay/scalar-gain acquisition; no payload-fitted correction')


def transition_cdr_screen(rate, *, initial_ppm=100., gap_bits=10000,
                          gap_frequency_step_ppm=0., seed=81, capture=None):
    """Event-driven ideal wrapped phase detector and bounded PI correction.

    Controller sees transition phase only, never injected frequency error.
    Initial reference-assisted frequency accuracy is an explicit assumption.
    """
    rng=np.random.default_rng(seed)
    phase=.2
    correction=0.
    source_error=initial_ppm*1e-6
    trace=[]
    elapsed_bits=0
    slips=0
    # Synthetic transition-rich acquisition; not an SDI encoded pattern.
    for gap in rng.integers(1,6,4096):
        gap=int(gap)
        elapsed_bits+=int(gap)
        phase+=gap*(source_error+correction)
        slips+=int(abs(phase)>=.5)
        measurement=(phase+rng.normal(0,5e-12*rate)+.5)%1-.5
        correction=float(np.clip(correction-.0002*measurement/gap,-.002,.002))
        phase-=.15*measurement
        trace.append(phase)
    acquired=max(abs(x) for x in trace[-256:])<.05 and slips==0
    residual=source_error+correction
    # With no transitions, no detector correction is possible.
    end_phase=phase+gap_bits*(residual+gap_frequency_step_ppm*1e-6)
    worst=max(abs(phase),abs(end_phase))+7*5e-12*rate
    # Independent payload bits determine transition events. Only the detector's
    # wrapped phase reaches the controller; bit labels are used after sampling.
    payload=np.random.default_rng(seed+1000).integers(0,2,4096)
    phase=end_phase
    gap_since_transition=0
    decoded=[]
    index_offsets=[]
    sample_times=[]
    for bit in range(len(payload)):
        phase+=source_error+gap_frequency_step_ppm*1e-6+correction
        gap_since_transition+=1
        if bit and payload[bit]!=payload[bit-1]:
            measurement=(phase+rng.normal(0,5e-12*rate)+.5)%1-.5
            correction=float(np.clip(correction-.0002*measurement/gap_since_transition,-.002,.002))
            phase-=.15*measurement
            gap_since_transition=0
        sample_times.append((bit+.5+phase)/rate)
        sampled_index=math.floor(bit+.5+phase)
        index_offsets.append(sampled_index-bit)
        decoded.append(int(payload[sampled_index]) if 0<=sampled_index<len(payload) else -1)
    errors=int(np.count_nonzero(np.asarray(decoded)!=payload))
    if capture is not None:capture.update(transmitted=payload.tolist(),received=decoded,sample_times=sample_times)
    return dict(line_rate_bps=rate,acquired=acquired,acquisition_bits=elapsed_bits,
                payload_bits=len(payload),payload_errors=errors,
                payload_identity_preserved=errors==0 and all(x==0 for x in index_offsets),
                maximum_bit_index_offset=max(abs(x) for x in index_offsets),
                final_unwrapped_phase_ui=phase,
                acquisition_s=elapsed_bits/rate,residual_ppm=residual*1e6,
                acquisition_cycle_slip_events=slips,gap_bits=gap_bits,
                gap_frequency_step_ppm=gap_frequency_step_ppm,
                gap_end_phase_ui=end_phase,worst_gap_error_ui=worst,
                timing_survives_gap=acquired and worst<.35,
                assumptions='Ideal wrapped transition detector, empirical PI gains, bounded correction, 5 ps IID transition jitter; no physical CDR qualification')


class RecoveredWordSource:
    """Incremental voltage-crossing payload CDR with one cached output word."""
    def __init__(self,bits,rate,phase_ui,residual_ppm,channel_tau_ui=.1):
        if not math.isfinite(channel_tau_ui) or channel_tau_ui<=0:raise ValueError('Positive channel time constant required')
        self.tau_ui=channel_tau_ui
        self.bits=list(bits);self.rate=rate;self.phase=phase_ui
        # External NRZ channel state at each transmitted bit boundary.
        self.boundaries=[-.2]
        decay=math.exp(-1/channel_tau_ui)
        for bit in self.bits:
            target=.2 if bit else -.2
            self.boundaries.append(target+(self.boundaries[-1]-target)*decay)
        self.detected_edges=0
        self.edge_errors=deque(maxlen=64)
        self.timing_qualified=False;self.first_qualified_bit=None
        self.qualification_losses=0
        self.frequency=residual_ppm*1e-6;self.correction=0.
        self.bit_index=0;self.gap=0;self.word_index=0
        self.pending=None;self.words=[];self.rng=np.random.default_rng(421)
        self.predicted=None
        self.bit_observer=None;self.last_timestamp=None
        self.detector_time_ui=None;self.detector_voltage=None
        self.latest_crossing_ui=None

    def bit(self,index):
        return self.bits[index] if 0<=index<len(self.bits) else 0

    def voltage(self,time_ui):
        if time_ui<0:return -.2
        index=math.floor(time_ui)
        if index>=len(self.bits):
            return -.2+(self.boundaries[-1]+.2)*math.exp(-(time_ui-len(self.bits))/self.tau_ui)
        target=.2 if self.bits[index] else -.2
        return target+(self.boundaries[index]-target)*math.exp(-(time_ui-index)/self.tau_ui)

    def crossing(self,index):
        if index<0 or index>=len(self.bits):return None
        before=self.boundaries[index];after=self.boundaries[index+1]
        if before*after>=0:return None
        target=.2 if self.bits[index] else -.2
        return -self.tau_ui*math.log(-target/(before-target))

    def forecast(self,index):
        if index!=self.word_index or self.pending is not None:
            raise ValueError('Consume current CDR word before requesting next')
        predicted=copy.copy(self)
        predicted.edge_errors=self.edge_errors.copy()
        predicted.rng=copy.deepcopy(self.rng)
        observations=[]
        predicted.bit_observer=lambda bit,qualified:observations.append((bit,qualified))
        timestamp=predicted._forecast_word()
        self.pending=predicted.pending
        self.predicted=(predicted,observations)
        return timestamp

    def _forecast_word(self):
        word=0
        for j in range(10):
            i=self.bit_index
            self.phase+=self.frequency+self.correction
            sample_time=i+.5+self.phase
            previous_time=self.detector_time_ui
            if previous_time is None:
                previous_time=sample_time-1.
                self.detector_voltage=self.voltage(previous_time)
            if sample_time<=previous_time:raise ValueError('Nonmonotonic receiver sampling clock')
            self.gap+=1
            crossings=[]
            # Four voltage observations on the receiver's own interval. No
            # source-bit index or analytic source-boundary crossing is queried.
            voltage=self.detector_voltage
            for at in np.linspace(previous_time,sample_time,5)[1:]:
                current=self.voltage(float(at))
                if voltage*current<0:
                    edge=previous_time+(float(at)-previous_time)*(-voltage)/(current-voltage)
                    crossings.append(edge)
                previous_time=float(at);voltage=current
            self.detector_time_ui=sample_time;self.detector_voltage=voltage
            # This decision precedes correction. All observed transitions are
            # in its past; loop updates affect only later sampling instants.
            sample=int(voltage>0)
            for edge in crossings:
                self.latest_crossing_ui=edge;self.detected_edges+=1
                error=(sample_time-.5-edge+self.rng.normal(0,5e-12*self.rate)+.5)%1-.5
                self.correction=float(np.clip(self.correction-.0002*error/max(1,self.gap),-.002,.002))
                self.phase-=.15*error;self.gap=0
                self.edge_errors.append(abs(error))
            if self.gap>64:self.edge_errors.clear()
            qualified=(len(self.edge_errors)==64 and max(self.edge_errors)<.1)
            if self.timing_qualified and not qualified:self.qualification_losses+=1
            self.timing_qualified=qualified
            if qualified and self.first_qualified_bit is None:self.first_qualified_bit=i
            word|=sample<<j
            if self.bit_observer is not None:self.bit_observer(sample,qualified)
            timestamp=sample_time/self.rate
            self.bit_index+=1
        self.pending=word;self.last_timestamp=timestamp
        return timestamp

    def commit(self,index):
        """Commit one due word; prediction alone cannot update lock/alignment."""
        if index!=self.word_index or self.pending is None:raise ValueError('No current CDR word')
        if self.predicted is not None:
            predicted,observations=self.predicted
            for name in ('phase','correction','gap','detected_edges','edge_errors',
                         'timing_qualified','first_qualified_bit','qualification_losses',
                         'bit_index','rng','last_timestamp','detector_time_ui','detector_voltage','latest_crossing_ui'):
                setattr(self,name,getattr(predicted,name))
            self.predicted=None
            if self.bit_observer is not None:
                for bit,qualified in observations:self.bit_observer(bit,qualified)

    def consume(self,index):
        if index!=self.word_index or self.pending is None:raise ValueError('No current CDR word')
        self.commit(index)
        value=self.pending;self.pending=None;self.word_index+=1;self.words.append(value)
        return value


class SerialHistoryUnavailable(ValueError):
    pass


class EmittedWordChannel(RecoveredWordSource):
    """External TX peer fixture fed only by actual emitted words.

    Ten-bit ideal serializer cadence and the existing one-pole channel/CDR.
    Histories are diagnostic storage, not proposed on-chip memory. Receiver
    forecasts cannot observe unelapsed or unsupplied channel intervals.
    """
    def __init__(self,rate=2.5e9,phase_ui=.35,residual_ppm=100.):
        super().__init__([],rate,phase_ui,residual_ppm)
        self.origin=None;self.available_ui=0.;self.emitted_words=0;self.time=0.

    def voltage(self,time_ui):
        if time_ui>=min(self.available_ui,len(self.bits)):
            raise SerialHistoryUnavailable('Receiver sample precedes channel availability')
        if time_ui<0:return -.2
        index=math.floor(time_ui)
        target=0. if self.bits[index] is None else (.2 if self.bits[index] else -.2)
        return target+(self.boundaries[index]-target)*math.exp(-(time_ui-index)/self.tau_ui)

    def crossing(self,index):
        if index>=0 and index+1>min(self.available_ui,len(self.bits)):
            raise SerialHistoryUnavailable('Detector interval has not completed')
        if index<0 or index>=len(self.bits):return None
        before=self.boundaries[index];after=self.boundaries[index+1]
        if before*after>=0:return None
        target=0. if self.bits[index] is None else (.2 if self.bits[index] else -.2)
        if target==0:return None
        return -self.tau_ui*math.log(-target/(before-target))

    def idle_until(self,time):
        """Explicit zero-differential idle after the last supplied word.

        Existing channel/CDR state persists. This diagnostic requires a restart
        on the original bit grid; arbitrary serializer-phase restart is unproven.
        """
        if self.origin is None or not math.isfinite(time) or time<self.time:
            raise ValueError('Idle requires an existing monotonic TX timeline')
        position=(time-self.origin)*self.rate;end=round(position)
        if abs(position-end)>1e-5 or end<len(self.bits):
            raise ValueError('Idle endpoint must follow supplied data on bit grid')
        count=end-len(self.bits);decay=math.exp(-1/self.tau_ui)
        for _ in range(count):
            self.bits.append(None);self.boundaries.append(self.boundaries[-1]*decay)
        self.advance(time)
        return count

    def advance(self,time):
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic peer time required')
        self.time=time
        if self.origin is None:return
        self.available_ui=max(0.,(time-self.origin)*self.rate)
        while True:
            try:timestamp=self.forecast(self.word_index)
            except SerialHistoryUnavailable:break
            if timestamp>time-self.origin:raise AssertionError('Future peer commit')
            self.consume(self.word_index)

    def emit(self,time,word):
        if type(word) is not int or not 0<=word<1024:raise ValueError('Ten-bit TX word required')
        if not math.isfinite(time) or time<self.time:raise ValueError('Monotonic TX time required')
        if self.origin is None:self.origin=time
        expected=self.origin+len(self.bits)/self.rate
        if abs(time-expected)>max(8*math.ulp(time),1e-18):
            raise ValueError('TX serializer cadence discontinuity')
        decay=math.exp(-1/self.tau_ui)
        for n in range(10):
            bit=(word>>n)&1;self.bits.append(bit)
            target=.2 if bit else -.2
            self.boundaries.append(target+(self.boundaries[-1]-target)*decay)
        self.emitted_words+=1
        self.advance(time)


class ObservedFrameAlignment:
    """External-fixture marker framing; no transmitted payload or bit index input.

    Hold one frame until its closing marker validates. This is a generic
    behavioral framing experiment, not a mandated wire encoding or chip ABI.
    """
    def __init__(self,marker,payload_bits):
        if not marker or any(type(b) is not int or b not in (0,1) for b in marker):
            raise ValueError('Require binary marker')
        if type(payload_bits) is not int or payload_bits<=0:
            raise ValueError('Require positive payload length')
        self.marker=tuple(marker);self.payload_bits=payload_bits
        self.window=deque(maxlen=len(marker));self.pending=None
        self.ready=False;self.losses=0;self.frames=0

    def invalidate(self):
        if self.ready:self.losses+=1
        self.ready=False;self.pending=None;self.window.clear()

    def observe(self,bit,timing_qualified):
        if type(bit) is not int or bit not in (0,1):raise ValueError('Require received bit')
        if not timing_qualified:
            self.invalidate();return None
        self.window.append(bit)
        if self.pending is not None:
            self.pending.append(bit)
            if len(self.pending)==self.payload_bits+len(self.marker):
                if tuple(self.pending[-len(self.marker):])==self.marker:
                    payload=self.pending[:self.payload_bits]
                    self.pending=[];self.ready=True;self.frames+=1
                    return payload
                self.invalidate()
                # Mismatch is an erasure, never a fabricated empty payload.
                return None
        elif tuple(self.window)==self.marker:
            self.pending=[]
        return None



def causal_compliance_cdr_screen():
    """Known PCIe Gen1 compliance pattern, not LTSSM/packet/compliance signoff."""
    from protocol_signals import pcie_gen1_compliance_bits
    pattern=tuple(pcie_gen1_compliance_bits());rows=[]
    for phase in (-3.,-.35,.35,3.):
      for ppm in (-100.,100.):
       for damaged in (False,True):
        bits=pcie_gen1_compliance_bits(160)
        if damaged:bits[3200:3360]=[0]*160
        cdr=RecoveredWordSource(bits,2.5e9,phase,ppm)
        window=deque(maxlen=40);since=None;cycles=0;losses=0;ready=False
        def observe(bit,timing):
            nonlocal since,cycles,losses,ready
            if not timing:
                if ready:losses+=1
                ready=False;since=None;window.clear();return
            window.append(bit)
            if since is None:
                if tuple(window)==pattern:since=0
                return
            since+=1
            if since==40:
                if tuple(window)==pattern:cycles+=1;ready=True;since=0
                else:
                    if ready:losses+=1
                    ready=False;since=None
        cdr.bit_observer=observe
        # End before the finite source boundary; no expected payload/index is
        # supplied to the monitor. Each accepted repetition matches observed bits.
        for index in range(630):cdr.forecast(index);cdr.consume(index)
        rows.append(dict(phase_ui=phase,residual_ppm=ppm,damaged=damaged,
            observed_complete_patterns=cycles,monitor_losses=losses,
            final_pattern_ready=ready,final_timing_ready=cdr.timing_qualified,
            scope='Observed pattern recognition plus causal sampled CDR; no host transport, SSC, physical jitter envelope or link training'))
    return dict(cases=rows,source='PCI Express Base Specification 2.1 section 4.2.8',
        scope='Finite receiver test with legal Gen1 compliance sequence and invalid constant-level interruption; not PCIe endpoint or PHY compliance.')


def observed_alignment_controls():
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payloads=np.random.default_rng(723).integers(0,2,(24,160)).tolist()
    framed=marker+[b for payload in payloads for b in payload+marker]
    results=[]
    for gap in (0,1000,10000):
        gate=ObservedFrameAlignment(marker,160);released=[]
        prefix=[0,1]*1020
        bits=prefix+framed+[0]*gap+framed+[0]*200
        source=RecoveredWordSource(bits,2.5e9,.35,100.)
        source.bit_observer=lambda bit,qualified: released.append(value) if (value:=gate.observe(bit,qualified)) is not None else None
        change_at=len(prefix)+len(framed)
        for index in range(len(bits)//10):
            if source.bit_index<=change_at<source.bit_index+10:source.frequency+=100e-6
            source.forecast(index);source.consume(index)
        assert released and all(frame in payloads for frame in released)
        expected=iter(payloads+payloads)
        for frame in released:
            assert any(candidate==frame for candidate in expected), 'Duplicated or reordered frame'
        assert gate.frames==len(released)
        # Both bursts must deliver whole, correct frames despite long-gap drift.
        assert len(released)>=44,(gap,len(released))
        results.append(dict(gap_bits=gap,released_frames=len(released),payload_bits_per_frame=160,
            frame_identity=True,ordered_without_duplicates=True,alignment_losses=gate.losses))
    gate=ObservedFrameAlignment(marker,160)
    assert all(gate.observe(b,True) is None for b in marker+payloads[0])
    assert not gate.ready
    assert gate.observe(marker[0],False) is None and gate.pending is None
    assert all(gate.observe(b,True) is None for b in marker+payloads[0]+[1-b for b in marker])
    assert not gate.ready
    return dict(cases=results,unconfirmed_frame_withheld=True,timing_loss_discards_pending=True,
        wrong_closing_marker_rejected=True,
        scope='Same CDR/channel across two bursts; received-bit marker checks only. Frame holdback is an external-fixture experiment; host integration, reference lifecycle and standard encodings remain open. Marker checks do not detect arbitrary payload corruption or balanced slips.')


class AlignedHostSource:
    """Bounded confirmed-frame queue; raw CDR events continue during erasures."""
    def __init__(self,source,marker,payload_bits):
        if payload_bits%10:raise ValueError('Frame must contain complete host words')
        self.source=source;self.alignment=ObservedFrameAlignment(marker,payload_bits)
        self.capacity=payload_bits//10;self.queue=deque();self.high=0
        self.accepted=[];self.delivered=[];self.active=True;self.generation=0
        source.bit_observer=self.observe

    def observe(self,bit,qualified):
        frame=self.alignment.observe(bit,qualified and self.active)
        if frame is None:return
        words=[sum(b<<j for j,b in enumerate(frame[i:i+10])) for i in range(0,len(frame),10)]
        if len(self.queue)+len(words)>self.capacity:raise ValueError('Alignment buffer overflow')
        self.queue.extend(words);self.accepted.extend(words);self.high=max(self.high,len(self.queue))

    def cancel(self):
        discarded=dict(confirmed_words=len(self.queue),
            candidate_bits=len(self.alignment.pending or ()),cached_cdr_word=self.source.pending is not None)
        self.active=False;self.generation+=1;self.queue.clear();self.alignment.invalidate()
        return discarded

    def callbacks(self):
        """Capture one host epoch's raw-word offset and time origin."""
        self.require_active()
        generation=self.generation;base=self.source.word_index
        origin=self.source.last_timestamp or 0.
        def check():
            if generation!=self.generation:raise ValueError('Stale aligned-source generation')
            self.require_active()
        def forecast(index):
            check();return self.forecast(base+index)-origin
        def valid(index):
            check();return self.valid(base+index)
        def consume(index):
            check();return self.consume(base+index)
        def cancel():
            check();return self.cancel()
        return dict(rx_event_time=forecast,rx_valid=valid,rx_source=consume,rx_cancel=cancel)

    def advance_disabled(self,words):
        if self.active or type(words) is not int or words<0:
            raise ValueError('Disabled source and nonnegative word count required')
        for _ in range(words):
            index=self.source.word_index
            if self.source.pending is None:self.source.forecast(index)
            self.source.consume(index)
        return self.source.last_timestamp

    def rearm(self):
        if self.active or self.source.pending is not None:
            raise ValueError('Retire disabled raw event before rearming')
        self.generation+=1;self.active=True
        self.alignment.invalidate()
        return self.callbacks()

    def require_active(self):
        if not self.active:raise ValueError('Cancelled aligned source')

    def forecast(self,index):
        self.require_active();return self.source.forecast(index)

    def valid(self,index):
        self.require_active()
        if index!=self.source.word_index or self.source.pending is None:
            raise ValueError('Forecast before querying validity')
        self.source.commit(index)
        return bool(self.queue)

    def consume(self,index):
        self.require_active()
        self.source.consume(index)
        if not self.queue:return 0
        word=self.queue.popleft();self.delivered.append(word);return word


def aligned_host_delivery():
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payloads=np.random.default_rng(723).integers(0,2,(24,160)).tolist()
    framed=marker+[b for payload in payloads for b in payload+marker]
    results=[]
    for gap in (0,1000,10000):
        observations=[]
        for chunks in ((120,),(7,33,80)):
            bits=[0,1]*1020+framed+[0]*gap+framed+[0]*200
            raw=RecoveredWordSource(bits,2.5e9,.35,200.)
            source=AlignedHostSource(raw,marker,160)
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
            chip.start();chip.advance(chip.ready_at)
            args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,
                rx_event_time=source.forecast,rx_source=source.consume,rx_valid=source.valid,rx_cancel=source.cancel)
            for frames in chunks:flow=chip.receive(frames=frames,**args)
            assert flow['fault'] is None and flow['pending_bits']==0
            delivered=chip.stream['rx_words'];assert delivered==source.accepted==source.delivered
            recovered=[[((w>>j)&1) for w in delivered[i:i+16] for j in range(10)] for i in range(0,len(delivered),16)]
            expected=iter(payloads+payloads)
            for frame in recovered:assert any(candidate==frame for candidate in expected)
            assert len(recovered)>=44 and source.high<=source.capacity
            assert chip.stream['invalid_rx_events']>0
            observations.append((delivered,flow,raw.bit_index,raw.phase,source.high,chip.stream['invalid_rx_events']))
        assert observations[0]==observations[1]
        results.append(dict(gap_bits=gap,host_frames_delivered=len(observations[0][0])//16,
            host_payload_identity=True,chunk_invariant=True,buffer_capacity_words=16,
            peak_buffer_words=source.high,invalid_source_events=chip.stream['invalid_rx_events']))
    return dict(cases=results,scope='Confirmed generic marker frames feed finite host queues; 200 ppm initial offset and persistent CDR/channel/host state. Standard framing, reference-loss lifecycle and false-marker envelope remain open.')


def aligned_reference_cancellation():
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payload=np.random.default_rng(723).integers(0,2,160).tolist()
    bits=[0,1]*1020+marker+(payload+marker)*100
    raw=RecoveredWordSource(bits,2.5e9,.35,200.)
    source=AlignedHostSource(raw,marker,160)
    chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.start();chip.advance(chip.ready_at)
    args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,
        rx_event_time=source.forecast,rx_source=source.consume,rx_valid=source.valid,rx_cancel=source.cancel)
    for _ in range(20):
        chip.receive(frames=1,**args)
        if source.queue and source.alignment.pending:break
    assert source.queue and source.alignment.pending and raw.pending is not None
    before=(raw.phase,raw.correction,raw.frequency,raw.bit_index,raw.pending,tuple(raw.boundaries))
    old_epoch=chip.epoch;discarded=chip.lose_reference()
    assert chip.epoch==old_epoch+1 and chip.stream is None and not source.active
    assert not source.queue and source.alignment.pending is None
    assert before==(raw.phase,raw.correction,raw.frequency,raw.bit_index,raw.pending,tuple(raw.boundaries))
    rejected=0
    for callback in (source.forecast,source.valid,source.consume):
        try:callback(raw.word_index)
        except ValueError:rejected+=1
        else:raise AssertionError('Cancelled event accepted')
    # Keep the same physical CDR evolving while host delivery is disabled.
    raw.consume(raw.word_index)
    for _ in range(30):raw.forecast(raw.word_index);raw.consume(raw.word_index)
    assert not source.queue and not source.alignment.ready
    assert raw.bit_index>before[3] and raw.phase!=before[0]
    return dict(discarded=discarded,stale_callbacks_rejected=rejected,
        physical_state_preserved_at_cancel=True,clock_continues_while_delivery_disabled=True,
        scope='Host reference-loss callback cancels adapter digital work without resetting raw CDR/channel. Cached raw word is a prediction, committed only when consumed during disabled evolution; standard framing remains open.')


def wired_reference_presence_controls():
    """Reference timeout cannot commit a forecast future CDR/alignment word."""
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payloads=np.random.default_rng(729).integers(0,2,(500,160)).tolist()
    bits=[0,1]*1020+marker+[b for payload in payloads for b in payload+marker]
    probe=RecoveredWordSource(bits,2.5e9,.35,200.);observed=[]
    probe.bit_observer=lambda bit,good:observed.append((bit,good))
    before=(probe.phase,probe.bit_index,probe.rng.bit_generator.state)
    predicted=probe.forecast(0)
    assert (probe.phase,probe.bit_index,probe.rng.bit_generator.state)==before
    assert not observed and probe.last_timestamp is None
    probe.consume(0)
    assert len(observed)==10 and probe.bit_index==10 and probe.last_timestamp==predicted
    states=[]
    for chunks in ((25,),(5,20)):
        raw=RecoveredWordSource(bits,2.5e9,.35,200.);source=AlignedHostSource(raw,marker,160)
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        chip.attach_reference([i*25e-9 for i in range(4001) if not 881<=i<1280])
        chip.start();chip.advance(chip.ready_at);origin=chip.time
        callbacks=source.callbacks()
        args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,**callbacks)
        for frames in chunks:flow=chip.receive(frames=frames,**args)
        assert flow['fault']=='reference_lost' and abs(chip.time-22.1e-6)<1e-18
        assert raw.last_timestamp<=chip.time-origin
        assert raw.bit_index==10*chip.stream['sample_index']
        assert raw.predicted is not None and raw.predicted[0].last_timestamp>=chip.time-origin
        delivered=chip.stream['rx_words']
        assert delivered and delivered==source.accepted[:len(delivered)]
        frames=[[((w>>j)&1) for w in delivered[i*16:(i+1)*16] for j in range(10)] for i in range(len(delivered)//16)]
        expected=iter(payloads)
        for frame in frames:assert any(candidate==frame for candidate in expected)
        states.append((flow,delivered,raw.bit_index,raw.phase,list(source.queue),list(source.alignment.pending or [])))
    assert states[0]==states[1]
    loss_bits=raw.bit_index;loss_time=chip.time
    discarded=chip.stop();assert raw.bit_index==loss_bits
    while origin+(raw.last_timestamp or 0)<33e-6:source.advance_disabled(1)
    chip.advance(origin+raw.last_timestamp);chip.start()
    while origin+raw.last_timestamp<chip.ready_at:source.advance_disabled(1)
    chip.advance(origin+raw.last_timestamp)
    restart_index=raw.bit_index;new=source.rearm();accepted_start=len(source.accepted)
    flow=chip.receive(frames=25,mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,**new)
    delivered=chip.stream['rx_words'];assert flow['fault'] is None and len(delivered)>160
    assert delivered==source.accepted[accepted_start:accepted_start+len(delivered)]
    frames=[[((w>>j)&1) for w in delivered[i*16:(i+1)*16] for j in range(10)] for i in range(len(delivered)//16)]
    expected=iter(payloads[max(0,(restart_index-2040-64)//224):])
    for frame in frames:assert any(candidate==frame for candidate in expected)
    return dict(loss_time_s=loss_time,committed_bits_at_loss=loss_bits,chunk_invariant=True,
        forecast_preserves_cdr_rng_and_alignment=True,discarded=discarded,
        recovered_complete_frames=len(frames),retained_cdr_channel=True,host_payload_identity=True,
        scope='Word-atomic CDR commits at recovered-word events; subword timing is not exposed. Pulse-presence monitor and generic marker alignment, not autonomous PLL/standard protocol qualification.')


def aligned_reference_recovery():
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payloads=np.random.default_rng(729).integers(0,2,(500,160)).tolist()
    bits=[0,1]*1020+marker+[b for payload in payloads for b in payload+marker]+[0]*1000
    raw=RecoveredWordSource(bits,2.5e9,.35,200.)
    source=AlignedHostSource(raw,marker,160)
    chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.start();chip.advance(chip.ready_at);physical_origin=chip.time
    old=source.callbacks();old_epoch=chip.epoch
    common=dict(mode=1,source_hz=250e6,sample_bits=10)
    for _ in range(20):
        chip.receive(frames=1,epoch=chip.epoch,**common,**old)
        if source.queue and source.alignment.pending:break
    assert source.queue and raw.pending is not None
    discard=chip.lose_reference();phase_at_loss=raw.phase;index_at_loss=raw.bit_index
    try:source.rearm()
    except ValueError:pass
    else:raise AssertionError('Cached old event reused')
    source.advance_disabled(200)
    chip.advance(physical_origin+raw.last_timestamp)
    chip.start()
    while physical_origin+raw.last_timestamp<chip.ready_at:source.advance_disabled(1)
    chip.advance(physical_origin+raw.last_timestamp)
    before=(raw.phase,raw.correction,raw.bit_index,raw.word_index)
    new=source.rearm()
    assert before==(raw.phase,raw.correction,raw.bit_index,raw.word_index)
    assert raw.bit_index>index_at_loss and raw.phase!=phase_at_loss
    stale=0
    for name,callback in old.items():
        try:callback() if name=='rx_cancel' else callback(0)
        except ValueError:stale+=1
        else:raise AssertionError('Old callback became valid after rearm')
    try:chip.receive(frames=1,epoch=old_epoch,**common,**new)
    except ValueError:pass
    else:raise AssertionError('Old host epoch accepted')
    accepted_start=len(source.accepted)
    for frames in (7,33):flow=chip.receive(frames=frames,epoch=chip.epoch,**common,**new)
    delivered=chip.stream['rx_words']
    assert flow['fault'] is None and len(delivered)>160
    assert delivered==source.accepted[accepted_start:accepted_start+len(delivered)]
    complete=len(delivered)//16
    frames=[[((w>>j)&1) for w in delivered[i*16:(i+1)*16] for j in range(10)] for i in range(complete)]
    # Score only against external payloads transmitted after the rearm position.
    first_possible=max(0,(before[2]-2040-64)//224)
    expected=iter(payloads[first_possible:])
    for frame in frames:assert any(candidate==frame for candidate in expected)
    assert complete>10
    return dict(discarded=discard,stale_callbacks_rejected=stale,old_host_epoch_rejected=True,
        physical_state_unchanged_by_rearm=True,raw_bits_advanced_while_disabled=before[2]-index_at_loss,
        recovered_complete_frames=complete,host_words=len(delivered),host_payload_identity=True,
        scope='Same CDR/channel and chip across cancellation, disabled clock evolution, startup guard and rearm. Generic marker frames only; asynchronous interruption timing and standard encodings remain open.')


def cdr_host_delivery(rate=1.485e9):
    results=[]
    fast_tau=.1*rate/1.485e9
    for step,tau in ((0.,fast_tau),(100.,fast_tau),(0.,2.)):
        capture={}
        timing=transition_cdr_screen(rate,gap_frequency_step_ppm=step,capture=capture)
        provider=RecoveredWordSource(capture['transmitted'],rate,timing['gap_end_phase_ui'],
            timing['residual_ppm']+step,channel_tau_ui=tau)
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=rate))
        chip.start();chip.advance(chip.ready_at)
        args=dict(mode=0 if rate<=1.25e9 else 1,source_hz=rate/10,sample_bits=10,epoch=0,
            rx_event_time=provider.forecast,rx_source=provider.consume)
        chip.receive(frames=7,**args)
        flow=chip.receive(frames=13,**args)
        assert provider.word_index==chip.stream['sample_index']
        assert provider.pending is not None and chip.stream['next_source_time'] is not None
        assert flow['fault'] is None and len(chip.stream['rx_words'])>=409
        delivered=chip.stream['rx_words'][:409]
        assert delivered==provider.words[:409]
        host_bits=[(word>>bit)&1 for word in delivered for bit in range(10)]
        errors=sum(a!=b for a,b in zip(host_bits,capture['transmitted']))
        assert (errors==0)==(step==0. and tau==fast_tau)
        results.append(dict(line_rate_bps=rate,channel_tau_s=tau/rate,channel_tau_ui=tau,detected_voltage_crossings=provider.detected_edges,cdr=timing,flow=flow,delivered_payload_bits=len(host_bits),
            host_bit_errors=errors,transport_preserves_cdr_output=True,
            scope='Incremental voltage-crossing CDR words/times drive host queue; acquisition initial condition comes from separate screen'))
    return results


def cold_cdr_host_delivery():
    """Continuous channel/CDR/host startup; external observer skips training only."""
    results=[]
    bits=np.random.default_rng(981).integers(0,2,8192).tolist()
    for rate in (1.25e9,2.5e9):
        for phase in (-.35,.35):
            for ppm in (-100.,100.):
                provider=RecoveredWordSource(bits,rate,phase,ppm,
                    channel_tau_ui=.1*rate/1.485e9)
                chip=BehavioralChip(Assumptions())
                chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=rate))
                chip.start();chip.advance(chip.ready_at)
                args=dict(mode=0 if rate<=1.25e9 else 1,source_hz=rate/10,
                    sample_bits=10,epoch=0,rx_event_time=provider.forecast,
                    rx_source=provider.consume)
                chip.receive(frames=7,**args)
                flow=chip.receive(frames=33,**args)
                delivered=chip.stream['rx_words'][:819]
                assert flow['fault'] is None and len(delivered)==819
                assert delivered==provider.words[:819]
                observed=[(word>>j)&1 for word in delivered for j in range(10)]
                # Prefix length is an external fixture guard, not a lock detector.
                errors=sum(a!=b for a,b in zip(observed[2040:],bits[2040:8190]))
                assert errors==0
                assert provider.first_qualified_bit is not None and provider.first_qualified_bit<2040
                results.append(dict(line_rate_bps=rate,initial_phase_ui=phase,
                    initial_frequency_ppm=ppm,training_guard_bits=2040,
                    first_timing_qualified_bit=provider.first_qualified_bit,
                    scored_payload_bits=6150,host_bit_errors=errors,
                    transport_preserves_cdr_output=True,
                    scope='Same channel/CDR state from initial phase through host payload; fixed external training guard plus transition-error qualification; idealized detector, word alignment/slips not qualified'))
    return results


def cdr_qualification_controls():
    # Qualification uses only observed crossings and local phase error. Silence
    # cannot fill the window; stale samples must not qualify after a long gap.
    silence=RecoveredWordSource([0]*1024,2.5e9,.35,100.)
    for i in range(100):silence.forecast(i);silence.consume(i)
    assert silence.first_qualified_bit is None and not silence.timing_qualified
    recovery=[]
    rng=np.random.default_rng(43)
    prefix=rng.integers(0,2,2040).tolist()
    payload=rng.integers(0,2,4090).tolist()
    for gap in (1000,10000):
        bits=prefix+[0]*gap+payload
        burst=RecoveredWordSource(bits,2.5e9,.35,100.)
        for i in range(204):burst.forecast(i);burst.consume(i)
        assert burst.timing_qualified
        # Independent source frequency change at the beginning of silence.
        burst.frequency+=100e-6
        stop=204+gap//10
        for i in range(204,stop):burst.forecast(i);burst.consume(i)
        assert not burst.timing_qualified and burst.qualification_losses>=1
        reacquired=None
        for i in range(stop,stop+409):
            burst.forecast(i);burst.consume(i)
            if burst.timing_qualified and reacquired is None:reacquired=(i-stop+1)*10
        assert reacquired is not None
        observed=[(word>>j)&1 for word in burst.words[stop:] for j in range(10)]
        guard=2040
        errors=sum(a!=b for a,b in zip(observed[guard:],payload[guard:]))
        assert (errors==0)==(gap==1000)
        recovery.append(dict(gap_bits=gap,frequency_step_ppm=100.,
            timing_requalified_after_bits=reacquired,scored_bits=len(payload)-guard,
            payload_errors=errors,qualification_proves_alignment=False))
    return dict(silence_rejected=True,transition_loss_revokes_qualification=True,
        recovery=recovery,window_edges=64,max_phase_error_ui=.1,max_gap_bits=64,
        scope='Provisional local timing-quality monitor, not protocol word lock; wrapped phase cannot detect whole-bit slips')


def clock_holdover_screen(line_rate_bps, *, frequency_error_ppm, gap_bits,
                          initial_error_ui=.05, jitter_s=5e-12, eye_half_width_ui=.35):
    """Open-loop phase accumulation while data supplies no timing transitions.

    Does not model acquisition or assert a protocol's maximum run length.
    All phases are measured against the transmitted bit period.
    """
    if (not math.isfinite(line_rate_bps) or line_rate_bps<=0 or
            not math.isfinite(frequency_error_ppm) or abs(frequency_error_ppm)>=1e6 or
            type(gap_bits) is not int or gap_bits<0 or
            not all(math.isfinite(x) and x>=0 for x in (initial_error_ui,jitter_s,eye_half_width_ui))):
        raise ValueError('Invalid holdover envelope')
    fractional=frequency_error_ppm*1e-6
    drift=gap_bits*abs(fractional/(1+fractional))
    total=initial_error_ui+drift+7*jitter_s*line_rate_bps
    return dict(line_rate_bps=line_rate_bps,frequency_error_ppm=frequency_error_ppm,
                gap_bits=gap_bits,gap_s=gap_bits/line_rate_bps,drift_ui=drift,
                worst_error_ui=total,eye_half_width_ui=eye_half_width_ui,
                holdover_within_assumed_eye=total<eye_half_width_ui,
                acquisition_verified=False)


def configuration_sweep(contract):
    """External recipes exercise generic knobs without adding silicon profiles."""
    results=[]
    for case in contract['behavioral_configuration_cases']:
        chip=BehavioralChip(Assumptions())
        engine=case['engine']
        chip.configure_numeric(engine=engine,timing=case.get('timing'),rf=case.get('rf'))
        chip.start();chip.advance(chip.a.startup_s)
        if engine=='rf':
            if case['fixture']=='proprietary_gfsk':
                wave=gfsk(np.random.default_rng(81).integers(0,2,64),rate=case['symbol_rate_hz'])
            elif case['fixture']=='lora_24':
                wave=lora(np.arange(8),bandwidth=case['bandwidth_hz'])
            else:wave=fixture(case['fixture'],case.get('variant',''))
            rate=case['rf']['sample_hz'];bits=2*case['rf'].get('converter_bits',12);mode=case.get('host_mode',0)
            frames=max(128,math.ceil((wave.duration+544/rate+(54.4e-6 if wave.kind=='he20' else 0))*(250e6 if mode==0 else 312.5e6)/64))
        else:
            wave=None;rate=case['timing']['line_rate_bps']/10;bits=10
            mode=int(rate>125e6);frames=128
        flow=chip.transfer(mode=mode,source_hz=rate,sample_bits=bits,frames=frames,epoch=0)
        power=power_budget(chip.resources,chip.a,flow,contract,mode=mode,dc_sink=case.get('electrical')=='dc_current_sink')
        quality=waveform_screen(wave,chip.a,power,settings=case['rf']) if wave else quality_budget(chip.resources,chip.a)
        assert flow['fault'] is None,case['id']
        timing=None
        if case.get('timing',{}).get('clock_source')=='forwarded_word':
            timing=forwarded_pll_acquisition(case['timing']['reference_hz'],noise_rms_hz=20000.)
            assert timing['acquisition_s']<=chip.a.startup_s
        acquisition_cases=[]
        if wave is not None:
            for offset in (-48000.,0.,48000.):
                observed=waveform_screen(wave,chip.a,power,settings=case['rf'],
                    carrier_offset_hz=offset,recover_carrier=True)
                covered=flow['simulated_s']>=observed['duration_s']+observed['training_and_guard_s']
                passed=(flow['fault'] is None and covered and power['conditional_screen_pass']
                        and observed['conditional_screen_pass'])
                acquisition_cases.append(dict(offset_hz=offset,quality=observed,
                    full_waveform_serviced=covered,conditional_system_pass=passed))
            assert all(row['full_waveform_serviced'] for row in acquisition_cases)
        results.append(dict(case=case,flow=flow,power=power,quality=quality,
            acquisition_cases=acquisition_cases,forwarded_timing=timing,
            conditional_system_pass=(flow['fault'] is None and power['conditional_screen_pass']
                and quality['conditional_screen_pass'] and (timing is None or timing['group_timing_ready']) and all(row['conditional_system_pass'] for row in acquisition_cases)),
            physical_qualification=False))
    # Reject mismatched x10 ratios, out-of-band settings, and live changes.
    for invalid in (lambda:validate_wire_timing(1.485e9,'forwarded_word',74.25e6),
                    lambda:validate_rf_settings(sample_hz=5e6,rx_cutoff_hz=9e6),
                    lambda:chip.configure_numeric(engine='rf',rf={})):
        try:invalid()
        except ValueError:pass
        else:raise AssertionError('Invalid configuration accepted')
    return results


def rf_distortion_diagnostics():
    """Controlled ablations; no claim of independent additive error powers."""
    a=Assumptions()
    quiet=replace(a,converter_enob=12.,sample_jitter_s=0.,
                  relative_lo_phase_rms_rad=0.,frontend_evm_rms=0.)
    power={'estimated_rail_v':{'RF':a.supply_v}}
    results=[]
    for name in ('wifi_he20','lora_24'):
        wave=fixture(name)
        for label,assumptions in (('nominal',a),('no_added_noise',quiet)):
            result=waveform_screen(wave,assumptions,power)
            results.append(dict(fixture=name,case=label,result=result))
        if name=='lora_24':
            for oversample in (16,32):
                dense=lora(wave.symbols,bandwidth=wave.metadata['bandwidth'],oversample=oversample)
                results.append(dict(fixture=name,case='source_oversample_'+str(oversample),
                    result=waveform_screen(dense,quiet,power)))
    return results


def carrier_offset_diagnostics(contract):
    a=Assumptions()
    power={'estimated_rail_v':{'RF':a.supply_v}}
    results=[]
    for name in ('wifi_he20','bluetooth_le','bluetooth_br_edr','ieee802154_24','lora_24'):
        wave=fixture(name)
        for offset in (-48000.,0.,48000.):
            quality=waveform_screen(wave,a,power,carrier_offset_hz=offset)
            recovered=waveform_screen(wave,a,power,carrier_offset_hz=offset,recover_carrier=True)
            results.append(dict(fixture=name,offset_hz=offset,quality=quality,recovered=recovered))
    for case in contract['behavioral_configuration_cases']:
        if case['engine']!='rf' or case['fixture'] not in ('bluetooth_le','lora_24'):continue
        wave=fixture(case['fixture'],case.get('variant','')) if case['fixture']!='lora_24' else lora(np.arange(8),bandwidth=case['bandwidth_hz'])
        for offset in (-48000.,48000.):
            recovered=waveform_screen(wave,a,power,settings=case['rf'],carrier_offset_hz=offset,recover_carrier=True)
            results.append(dict(fixture=case['fixture'],configuration=case['id'],offset_hz=offset,recovered=recovered))
    return results


def burst_robustness(contract):
    """Longer independently generated payloads, same finite transport and rail model."""
    results=[]
    for name in ('wifi_he20','bluetooth_le','lora_24'):
        case=next(c for c in contract['behavioral_configuration_cases'] if c.get('fixture')==name)
        for seed in (17,53,109):
            rng=np.random.default_rng(seed)
            if name=='wifi_he20':wave=he20(rng.integers(0,2,234*16))
            elif name=='bluetooth_le':wave=gfsk(rng.integers(0,2,256))
            else:wave=lora(rng.integers(0,128,32),bandwidth=case['bandwidth_hz'])
            chip=BehavioralChip(Assumptions())
            chip.configure_numeric(engine='rf',rf=case['rf'])
            chip.start();chip.advance(chip.a.startup_s)
            rate=case['rf']['sample_hz']
            duration=wave.duration+544/rate+(54.4e-6 if name=='wifi_he20' else 0)
            flow=chip.transfer(mode=0,source_hz=rate,sample_bits=24,
                frames=math.ceil(duration*250e6/64),epoch=0)
            power=power_budget(chip.resources,chip.a,flow,contract,mode=0)
            quality=waveform_screen(wave,chip.a,power,seed=seed,settings=case['rf'],
                carrier_offset_hz=48000.,recover_carrier=True)
            assert flow['fault'] is None and flow['simulated_s']>=duration
            results.append(dict(fixture=name,seed=seed,payload_symbols=len(wave.symbols),
                flow=flow,power=power,quality=quality,
                conditional_system_pass=power['conditional_screen_pass'] and quality['conditional_screen_pass']))
    return results


def exclusive_handover_check():
    chip=BehavioralChip(Assumptions())
    stages=[]
    def reject(operation):
        before=(chip.time,chip.epoch,chip.state,dict(chip.resources))
        try:operation()
        except ValueError:pass
        else:raise AssertionError('Illegal handover traffic accepted')
        assert before==(chip.time,chip.epoch,chip.state,chip.resources)
    for engine in ('rf','wire','rf','wire'):
        previous_epoch=chip.epoch-1
        if engine=='rf':
            chip.configure_numeric(engine=engine,rf=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6))
            assert 'clock_source' not in chip.resources
            rate,bits,mode=10e6,24,0
        else:
            chip.configure_numeric(engine=engine,timing=dict(line_rate_bps=1.485e9/1.001,
                clock_source='forwarded_word',reference_hz=148.5e6/1.001))
            assert 'sample_hz' not in chip.resources
            rate,bits,mode=chip.resources['line_rate_bps']/10,10,1
        args=dict(mode=mode,source_hz=rate,sample_bits=bits,epoch=chip.epoch,frames=16)
        chip.start()
        reject(lambda:chip.transfer(**args))
        chip.advance(chip.ready_at)
        reject(lambda:chip.transfer(**dict(args,epoch=previous_epoch)))
        reject(lambda:chip.transfer(**dict(args,source_hz=rate/2)))
        reject(lambda:chip.configure_numeric(engine='rf',rf={}))
        flow=chip.transfer(**args)
        assert flow['fault'] is None
        discarded=chip.stop()
        assert discarded==dict(rx_bits=flow['pending_bits'],tx_bits=flow['tx']['pending_bits'])
        assert chip.stream is None
        stages.append(dict(engine=engine,epoch=chip.epoch-1,flow=flow,discarded=discarded))
    return stages


def blocker_screen(contract):
    results=[]
    case=next(c for c in contract['behavioral_configuration_cases'] if c.get('fixture')=='bluetooth_le')
    a=Assumptions();wave=fixture('bluetooth_le')
    for cutoff in (1e6,4e6):
        settings=dict(case['rf'],rx_cutoff_hz=cutoff)
        for level in (-20.,0.,20.,40.):
            blocker=dict(offset_hz=3e6,relative_power_db=level)
            result=waveform_screen(wave,a,{'estimated_rail_v':{'RF':3.3}},settings=settings,
                recover_carrier=True,blocker=blocker,rx_order=1)
            results.append(dict(settings=settings,quality=result))
    for level in (-20.,0.,20.,40.):
        settings=dict(case['rf'],rx_cutoff_hz=1e6)
        result=waveform_screen(wave,a,{'estimated_rail_v':{'RF':3.3}},settings=settings,
            recover_carrier=True,blocker=dict(offset_hz=3e6,relative_power_db=level),rx_order=5)
        results.append(dict(settings=settings,quality=result))
    for saturation in (.5,1.,2.):
        for level in (0.,20.):
            settings=dict(case['rf'],rx_cutoff_hz=1e6)
            result=waveform_screen(wave,a,{'estimated_rail_v':{'RF':3.3}},settings=settings,
                recover_carrier=True,blocker=dict(offset_hz=3e6,relative_power_db=level),
                rx_order=5,frontend_saturation_v=saturation)
            results.append(dict(settings=settings,quality=result))
    assert all(row['quality']['adc_clipped_samples']>0 for row in results if row['quality']['blocker']['relative_power_db']==40. and row['quality']['rx_filter_order']==1)
    return results


def bandwidth_tradeoff(contract):
    base=next(c['rf'] for c in contract['behavioral_configuration_cases'] if c.get('fixture')=='bluetooth_le')
    results=[]
    for cutoff in (1e6,1.25e6,1.5e6):
        settings=dict(base,rx_cutoff_hz=cutoff)
        observations=[]
        for seed in (17,53,109):
            wave=fixture('bluetooth_le',seed=seed)
            for offset in (-48000.,0.,48000.):
                q=waveform_screen(wave,Assumptions(),{'estimated_rail_v':{'RF':3.25}},
                    settings=settings,seed=seed,carrier_offset_hz=offset,recover_carrier=True)
                observations.append(dict(seed=seed,offset_hz=offset,quality=q))
        blocker=waveform_screen(fixture('bluetooth_le'),Assumptions(),{'estimated_rail_v':{'RF':3.25}},
                    settings=settings,recover_carrier=True,blocker=dict(offset_hz=3e6,relative_power_db=20.))
        results.append(dict(cutoff_hz=cutoff,observations=observations,
            worst_evm_rms=max(x['quality']['evm_rms'] for x in observations),
            all_clean_cases_pass=all(x['quality']['conditional_screen_pass'] for x in observations),
            blocker=blocker,scope='Fixed 3.25 V rail, fifth-order filter; no frontend compression'))
    return results


def supply_impedance(frequency_hz, resistance_ohm, inductance_h, capacitance_f):
    """Small-signal load impedance of series R/L feed with local shunt C."""
    if not all(math.isfinite(x) and x>=0 for x in (frequency_hz,resistance_ohm,inductance_h,capacitance_f)) or resistance_ohm<=0:
        raise ValueError('Passive finite supply network required')
    angular=2*math.pi*frequency_hz
    series=resistance_ohm+1j*angular*inductance_h
    return series/(1+1j*angular*capacitance_f*series)


def shared_rail_controls():
    rail=SharedRail();charge=25e-12;dt=1.7e-9
    rail.load(charge);rail.advance(dt)
    decay=math.exp(-dt/(rail.r*rail.c))
    assert math.isclose(rail.droop,charge/rail.c*decay,rel_tol=1e-13)
    expected=-2*math.pi*rail.lo_sensitivity*charge*rail.r*(1-decay)
    assert math.isclose(rail.phase,expected,rel_tol=1e-13)
    assert abs(rail.report()['charge_balance_error_c'])<1e-25
    from scipy.linalg import expm
    for inductance in (.1e-9,1e-9,5e-9,10e-9):
        for dt in (.1e-9,3e-9,40e-9):
            network=SharedRail(inductance_h=inductance);network.load(charge)
            network.current=-.001;initial=np.array([network.droop,network.current,0.])
            matrix=np.array([[0,-1/network.c,0],[1/network.l,-network.r/network.l,0],[1,0,0]])
            reference=expm(matrix*dt)@initial;network.advance(dt)
            assert np.allclose([network.droop,network.current],reference[:2],rtol=1e-9,atol=1e-13)
            assert math.isclose(network.phase,-2*math.pi*network.lo_sensitivity*reference[2],rel_tol=1e-9,abs_tol=1e-12)
            assert abs(network.report()['charge_balance_error_c'])<1e-25
    network=SharedRail(inductance_h=5e-9);network.load(charge);network.current=-.005
    initial=np.array([network.droop,network.current]);matrix=np.array([[0,-1/network.c],[1/network.l,-network.r/network.l]])
    sampled=[(expm(matrix*t)@initial)[0] for t in np.linspace(0,40e-9,1001)]
    sampled_peak=max(sampled);sampled_trough=min(sampled)
    network.advance(40e-9)
    assert sampled_peak-1e-12<=network.nominal-network.minimum_v<=sampled_peak+1e-5
    assert -sampled_trough-1e-12<=network.maximum_v-network.nominal<=-sampled_trough+1e-5
    settings=dict(sample_hz=20e6,tx_cutoff_hz=10e6,rx_cutoff_hz=5e6,rx_filter_order=5,converter_bits=12)
    samples=.2*np.exp(.1j*np.arange(400))
    baseline,_=live_host_rf_observation(samples,settings)
    disabled,zero=live_host_rf_observation(samples,settings,rail_config=dict(host_coupling=0.,converter_charge_c=0.))
    assert np.array_equal(baseline,disabled) and zero['shared_rail']['injected_charge_c']==0
    isolated,isolation=live_host_rf_observation(samples,settings,rail_config=dict(host_coupling=1.,lo_hz_per_v=0.,rf_gain_fraction=0.))
    assert np.array_equal(baseline,isolated) and isolation['shared_rail']['injected_charge_c']>0
    whole,report=live_host_rf_observation(samples,settings,rail_config={})
    parts,split=live_host_rf_observation(samples,settings,rail_config={},chunks=(17,report['frames']-17))
    assert np.array_equal(whole,parts) and report==split
    assert not np.array_equal(whole,baseline)
    for parameters,completed in ((dict(capacitance_f=10e-12,host_coupling=0.),0),
                                 (dict(capacitance_f=10e-12,host_coupling=1.,converter_charge_c=0.),1)):
        try:live_host_rf_observation(samples,settings,rail_config=parameters,chunks=(17,report['frames']-17))
        except LiveRFTransportFailure as error:
            failed=error.report
            assert failed['flow']['fault']=='shared_supply_low' and failed['dac_samples']==completed
            assert failed['flow']['produced_bits']==24*completed
            assert failed['flow']['tx']['consumed_bits']==24*completed
        else:raise AssertionError('Supply failure returned a normal RF observation')
    chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
    chip.attach_shared_rail(capacitance_f=10e-12,host_coupling=0.)
    chip.attach_rf_stream(lambda i:.2j);chip.start();chip.advance(chip.ready_at)
    args=dict(mode=0,source_hz=20e6,sample_bits=24,frames=1,epoch=0)
    failure=chip.receive(**args);assert failure['fault']=='shared_supply_low'
    state=chip.shared_rail.report()
    try:chip.receive(**args)
    except ValueError:pass
    else:raise AssertionError('Faulted RF stream resumed without recovery')
    assert chip.rf_stream.index==0 and chip.shared_rail.report()==state
    for during_startup in (False,True):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_shared_rail(resistance_ohm=1000.,host_coupling=0.)
        chip.attach_rf_stream(lambda i:.1j);chip.start();chip.advance(chip.ready_at)
        assert chip.receive(**args)['fault'] is None
        chip.stop();core=chip.parked_rf;count=core.index;state=core.rx.state.copy()
        event_time=chip.time-chip.rf_idle_phase/core.actual_sample_hz
        chip.shared_rail.load(2e-9)  # Deliberately adverse external charge step.
        if during_startup:chip.resume_rf_stream(lambda i:.1j);chip.start()
        try:chip.advance(chip.time+1e-6)
        except SupplyRangeError:pass
        else:raise AssertionError('Idle/startup supply failure escaped')
        assert chip.state=='fault' and chip.ready_at==math.inf
        assert chip.time==chip.shared_rail.time==event_time
        assert core.index==count and np.array_equal(core.rx.state,state) and chip.parked_rf is core
        report=chip.shared_rail.report()
        for action in (lambda:chip.advance(chip.time+1e-6),chip.start,lambda:chip.receive(**dict(args,epoch=chip.epoch))):
            try:action()
            except ValueError:pass
            else:raise AssertionError('Faulted idle/startup continued')
        assert chip.shared_rail.report()==report
    return dict(idle_startup_fault_time_and_state=True,supply_failure_accounting=True,fault_prevents_further_events=True,analytic_rc_and_phase=True,rlc_matrix_exponential_agreement=True,interior_voltage_extrema=True,charge_balance=True,zero_coupling_identity=True,
        coupled_chunk_invariant=True,changes_delivered_samples=True,disabled_effects_identity_with_live_charge=True,
        scope='Charge impulses and exact RC/RLC relaxation including interior extrema; no validated package, regulator, H2D input or control-header data switching model. Non-payload D2H data holds; forwarded-clock activity is the existing half-rise/word assumption.')


def host_coupling_screen(contract):
    a=Assumptions()
    # Same switched-capacitance law as the HOST_A/B average-current budget.
    host_dynamic_a=(10*a.host_data_rising_probability+.5)*250e6*a.host_output_cap_f*a.supply_v
    settings=next(c['rf'] for c in contract['behavioral_configuration_cases'] if c.get('fixture')=='wifi_he20')
    results=[]
    for coupling in (.1,1.):
        for frequency in (1e6,10e6):
            network=dict(resistance_ohm=2.,inductance_h=5e-9,capacitance_f=1e-9)
            impedance=supply_impedance(frequency,**network)
            current_peak=host_dynamic_a*coupling
            ripple=dict(amplitude_v=current_peak*abs(impedance),frequency_hz=frequency,
                        lo_sensitivity_hz_per_v=10e6)
            quality=waveform_screen(fixture('wifi_he20'),a,{'estimated_rail_v':{'RF':3.25}},
                settings=settings,recover_carrier=True,supply_ripple=ripple)
            results.append(dict(network=network,host_dynamic_current_a=host_dynamic_a,
                coupling_fraction=coupling,current_peak_a=current_peak,
                impedance_magnitude_ohm=abs(impedance),quality=quality,
                scope='Sinusoidal activity envelope and shared-path fraction are hypotheses; no extracted package model'))
    assert supply_impedance(0.,2.,5e-9,1e-9)==2.
    assert abs(supply_impedance(1e6,2.,5e-9,0.)-(2+1j*2*math.pi*1e6*5e-9))<1e-12
    return results


def supply_ripple_screen(contract):
    settings=next(c['rf'] for c in contract['behavioral_configuration_cases'] if c.get('fixture')=='wifi_he20')
    wave=fixture('wifi_he20');a=Assumptions();power={'estimated_rail_v':{'RF':3.25}}
    results=[]
    baseline=waveform_screen(wave,a,power,settings=settings,recover_carrier=True)
    for sensitivity in (0.,1e6,10e6):
        ripple=dict(amplitude_v=.05,frequency_hz=1e6,lo_sensitivity_hz_per_v=sensitivity)
        q=waveform_screen(wave,a,power,settings=settings,recover_carrier=True,supply_ripple=ripple)
        results.append(dict(quality=q,baseline=baseline['equalized']['evm_rms']))
    zero=dict(amplitude_v=0.,frequency_hz=1e6,lo_sensitivity_hz_per_v=10e6)
    q=waveform_screen(wave,a,power,settings=settings,recover_carrier=True,supply_ripple=zero)
    assert q['equalized']==baseline['equalized']
    assert not results[-1]['quality']['conditional_screen_pass']
    return results


def acquire_gfsk_prefix(observed,known_prefix,maximum_start=128):
    """Bounded frequency-template correlation; no payload symbols or true start."""
    measured=np.angle(observed[1:]*observed[:-1].conj())
    reference=np.angle(known_prefix.samples[1:]*known_prefix.samples[:-1].conj())
    skip=known_prefix.metadata['delay']
    reference=reference[skip:-4*known_prefix.metadata['sps']]
    reference=reference-reference.mean()
    best=(-1.,None)
    for start in range(maximum_start+1):
        row=measured[start+skip:start+skip+len(reference)]
        if len(row)!=len(reference):break
        row=row-row.mean()
        denominator=np.linalg.norm(row)*np.linalg.norm(reference)
        score=float(row@reference/denominator) if denominator>1e-15 else 0.
        if score>best[0]:best=(score,start)
    if best[0]<.8:raise ValueError('Known GFSK prefix not acquired')
    return best[1],best[0]


def rf_transmit_without_rx():
    """RX host service must not own the analog transmit clock."""
    results=[]
    for bits in (8,12):
        mode=1 if bits==8 else 0;fs=20e6 if bits==8 else 10e6;width=2*bits
        mask=(1<<bits)-1;scale=1<<(bits-1)
        settings=dict(sample_hz=fs,tx_cutoff_hz=fs/2,rx_cutoff_hz=fs/8,rx_filter_order=5,converter_bits=bits)
        def make():
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
            def source(index):
                code=chip.stream['tx_buffer']&((1<<width)-1);i=code&mask;q=(code>>bits)&mask
                return ((i if i<scale else i-2*scale)+1j*(q if q<scale else q-2*scale))/scale
            chip.attach_rf_stream(source,offset_hz=48000.,**declared_rf_noise(.2,bits))
            chip.start();chip.advance(chip.ready_at);return chip
        args=dict(mode=mode,source_hz=fs,sample_bits=width,epoch=0,
                  tx_source=lambda i:((i*73)^(i>>4)^0x155)&1023)
        duplex=make();whole=make();parts=make()
        full=duplex.transfer(frames=25,**args)
        one=whole.transfer(frames=25,directions=('tx',),**args)
        parts.transfer(frames=7,directions=('tx',),**args)
        split=parts.transfer(frames=18,directions=('tx',),**args)
        assert one==split and one['fault'] is None and full['fault'] is None
        count=one['tx']['consumed_bits']//width
        assert count>0 and all(c.rf_stream.index==count for c in (duplex,whole,parts))
        assert one['produced_bits']==one['returned_bits']==one['pending_bits']==0
        for candidate in (whole,parts):
            assert candidate.stream['tx_samples']==duplex.stream['tx_samples']
            assert candidate.rf_stream.tx.state==duplex.rf_stream.tx.state
            assert np.array_equal(candidate.rf_stream.rx.state,duplex.rf_stream.rx.state)
            assert candidate.rf_stream.previous_tx==duplex.rf_stream.previous_tx
            assert candidate.rf_stream.rng.bit_generator.state==duplex.rf_stream.rng.bit_generator.state
            assert candidate.rf_stream.phase_rng.bit_generator.state==duplex.rf_stream.phase_rng.bit_generator.state
        empty=make();fault=empty.transfer(frames=1,directions=('tx',),tx_prefill_bits=0,**args)
        assert fault['fault']=='underflow' and empty.rf_stream.index==0
        results.append(dict(converter_bits=bits,transmitted_samples=count,rx_host_bits=0,
            matches_duplex_analog_state=True,chunk_invariant=True,underflow_prevents_analog_step=True))
    return dict(cases=results,scope='TX-only host service advances the existing combined RF core. Receiver output is discarded; receiver power gating and independent remote RX are not modeled by this control.')


def lo_clock_controls():
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    edges=[i*25e-9 for i in range(4001)]
    def make(reference_edges=edges,**parameters):
        chip=BehavioralChip(Assumptions(startup_s=0.));chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_reference(reference_edges);chip.attach_lo_clock(max_step_s=6.25e-9,**parameters)
        source=lambda index:complex((chip.stream['tx_buffer']&255)/2048,0)
        chip.attach_rf_stream(source);chip.start()
        return chip,source
    chip,source=make();chip.advance(0.);assert chip.state=='acquiring'
    chip.advance(100e-9);assert chip.state=='acquiring'
    chip.advance(2e-6);assert chip.state=='active' and chip.lo_clock.first_lock_time<chip.time
    args=dict(mode=0,source_hz=10e6,sample_bits=24,frames=5,epoch=0,tx_source=lambda i:0x155)
    first=chip.transfer(**args);assert first['fault'] is None
    core=chip.rf_stream;clock=chip.lo_clock;count=core.index
    clock.disturb(chip.time,phase_cycles=.2)
    expected_loss=clock.next_detector
    failed=chip.transfer(**args)
    assert failed['fault']=='lo_unqualified' and chip.time==clock.time==expected_loss
    assert chip.state=='fault' and core.index>=count
    phase=clock.error;integral=clock.integral;chip.stop()
    assert chip.lo_clock is clock and clock.error==phase and clock.integral==integral
    chip.advance(chip.time+1e-6);chip.resume_rf_stream(source);chip.start();chip.advance(chip.time+3e-6)
    assert chip.state=='active' and chip.lo_clock is clock and chip.parked_rf is core
    recovered=chip.transfer(**{**args,'epoch':chip.epoch});assert recovered['fault'] is None and chip.rf_stream is core
    impossible,_=make(free_hz=2.7e9);impossible.advance(5e-6)
    assert impossible.state=='acquiring' and not impossible.lo_clock.locked
    try:impossible.transfer(**args)
    except ValueError:pass
    else:raise AssertionError('Untunable clock admitted payload')
    # Active acquisition cannot be manufactured by polling the same timestamp.
    same,_=make();same.advance(100e-9);good=same.lo_clock.good;comparisons=same.lo_clock.comparisons
    for _ in range(10):same.advance(same.time)
    assert same.lo_clock.good==good and same.lo_clock.comparisons==comparisons
    missing,_=make(reference_edges=[t for i,t in enumerate(edges) if not 881<=i<1280])
    missing.advance(20e-6);gap=missing.transfer(**{**args,'frames':25})
    assert gap['fault']=='reference_lost' and abs(missing.time-22.1e-6)<1e-18
    assert missing.lo_clock.time==missing.time and missing.lo_clock.next_detector==32e-6
    return dict(first_lock_s=clock.first_lock_time,phase_step_loss_s=expected_loss,
        fixed_guard_disabled=True,phase_step_blocks_payload=True,untunable_clock_rejected=True,
        repeated_time_cannot_qualify=True,retained_lo_and_rf_recovery=True,missing_reference_advances_same_lo=True,
        scope='Sampled detector PI/VCO with eight phase/slope observations. Parameters and perfect detector measurement are hypotheses; converter cadence remains fixed. Live PLL rail coupling has separate controls.')


def host_activity_controls(allocation='legacy'):
    """Decode both actual buses and independently sum their switching charge."""
    from stream_codec import Receiver
    rows=[]
    for bits,mode in ((12,0),(8,1)):
        settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=bits)
        def make(input_charge=.3e-12):
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
            chip.configure_transport(allocation)
            chip.attach_shared_rail(full_host_activity=True,input_transition_charge_c=input_charge)
            chip.attach_rf_stream(lambda i:complex((chip.stream['tx_buffer']&127)/1024,0))
            chip.start();chip.advance(chip.ready_at)
            rx=[];tx=[];original_rx=chip.shared_rail.host_word;original_tx=chip.shared_rail.host_input
            def output(word):rx.append(word);original_rx(word)
            def input_word(word):tx.append(word);original_tx(word)
            chip.shared_rail.host_word=output;chip.shared_rail.host_input=input_word
            return chip,rx,tx
        word=lambda i:((i*73)^(i>>4)^0x155)&1023
        args=dict(mode=mode,source_hz=10e6,sample_bits=2*bits,epoch=0,tx_source=word)
        chip,rx,tx=make();flow=chip.transfer(frames=5,**args)
        split,srx,stx=make();split.transfer(frames=2,**args);other=split.transfer(frames=3,**args)
        assert flow==other and rx==srx and tx==stx and flow['fault'] is None
        assert chip.shared_rail.report()==split.shared_rail.report()
        def decode(words):
            decoder=Receiver(mode,owner='iq' if allocation=='exclusive' else None);payload=[]
            for value in words:
                event=decoder.feed(value)
                if event is not None and event[0]=='iq':payload.append(event[1])
            assert decoder.pos==0 and not decoder.fault
            return payload
        assert decode(rx)==chip.stream['rx_words']
        assert decode(tx)==[word(i) for i in range(flow['tx']['accepted_bits']//10)]
        rises=.5*len(rx);previous=0
        for value in rx:rises+=(value&~previous&1023).bit_count();previous=value
        transitions=len(tx);previous=0
        for value in tx:transitions+=(value^previous).bit_count();previous=value
        rail=chip.shared_rail
        expected=rises*rail.host_cap*rail.nominal*rail.host_coupling+transitions*rail.input_charge+rail.converter_events*rail.converter_charge
        assert math.isclose(rail.charge,expected,rel_tol=1e-12,abs_tol=1e-22)
        assert rail.input_transitions==transitions and rail.input_events==len(tx)==320
        assert math.isclose(rail.input_total_charge,transitions*rail.input_charge,rel_tol=1e-12)
        faulted,_,_=make(2e-9);failed=faulted.transfer(frames=1,**args)
        assert failed['fault']=='shared_supply_low' and faulted.shared_rail.input_events==1
        count=faulted.rf_stream.index
        try:faulted.transfer(frames=1,**args)
        except ValueError:pass
        else:raise AssertionError('Input-load fault allowed more traffic')
        assert faulted.rf_stream.index==count and faulted.shared_rail.input_events==1
        rows.append(dict(converter_bits=bits,host_mode=mode,decoded_buses=True,
            transmitted_host_words=len(tx),received_host_words=len(rx),input_transitions=transitions,
            expected_total_charge_c=expected,measured_total_charge_c=rail.charge,
            chunk_invariant=True,input_load_fault_detected=True))
    return dict(cases=rows,scope='Existing non-feedback metadata/guard, payload and zero padding drive both buses. Input charge is effective local receiver charge per transition, not externally supplied FPGA line charge. Physical values and feedback-header ABI remain unqualified.')


def lo_integration_controls():
    """Compare exact intervals with the retained adaptive RK implementation."""
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    rows=[]
    for inductance,phase,bandwidth in ((0.,.2,1e6),(5e-9,-.2,1e6),(5e-9,.4,2e6)):
        pair=[]
        for analytic in (False,True):
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
            chip.attach_reference([i*25e-9 for i in range(401)])
            chip.attach_lo_clock(analytic=analytic,max_step_s=.5e-9,phase_cycles=phase,bandwidth_hz=bandwidth,noise_rms_hz=100000.)
            chip.attach_shared_rail(inductance_h=inductance);chip.start()
            for i in range(32):
                chip.advance(1e-6+i*13e-9);chip.shared_rail.load((1+i%3)*20e-12)
            chip.advance(2e-6);pair.append(chip.lo_clock)
        a,b=pair
        phase_error=abs(a.error-b.error);integral_error=abs(a.integral-b.integral)
        assert phase_error<2e-9 and integral_error<2e-8
        assert a.comparisons==b.comparisons and a.locked==b.locked and a.first_lock_time==b.first_lock_time
        rows.append(dict(inductance_h=inductance,initial_phase_cycles=phase,bandwidth_hz=bandwidth,
            phase_difference_cycles=phase_error,integral_difference_v=integral_error,
            lock_observations_match=True))
    outputs=[]
    for analytic in (False,True):
        samples,report=live_host_rf_observation(np.full(256,.2+.1j),settings,
            lo_config=dict(analytic=analytic,max_step_s=6.25e-9,noise_rms_hz=100000.),
            rail_config=dict(host_coupling=.1,inductance_h=5e-9))
        outputs.append(samples)
    assert np.array_equal(*outputs)
    held=ReferenceDrivenLO([i*25e-9 for i in range(9)])
    held.present=False;held.hold_voltage=held.rail
    held.advance(100e-9)
    expected=.2+(40e6-(2.38e9+200e6)/60)*100e-9
    assert abs(held.error-expected)<1e-14 and held.saturation_time==100e-9
    return dict(cases=rows,delivered_samples_identical=True,held_clamp_phase_and_duration_checked=True,
        scope='Exact held-detector unsaturated intervals integrate passive supply and finite spectral noise. Saturation boundaries retain adaptive RK. Independent RK comparisons include RC, RLC and initially saturated control; no physical assumptions or quality thresholds changed.')


def lo_supply_controls():
    """Independent RC phase integral and live retained PLL/rail coupling checks."""
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    def make(step):
        chip=BehavioralChip(Assumptions(startup_s=0.));chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_reference([i*25e-9 for i in range(4001)])
        chip.attach_lo_clock(free_hz=2.4e9,phase_cycles=0.,max_step_s=step,analytic=False)
        chip.attach_shared_rail();return chip
    expected=-2*math.pi*10e6*.1*2e-9*(1-math.exp(-25e-9/2e-9))
    values=[]
    for step in (.5e-9,.25e-9):
        chip=make(step);chip.lo_clock.set_reference(False,0.)
        chip.shared_rail.load(100e-12);chip.advance(25e-9)
        phase=-2*math.pi*60*chip.lo_clock.error
        assert abs(phase-expected)<2e-9
        values.append(phase)
        # The same rail phase must not be applied a second time in the RF path.
        core=SampledRFStream(settings,noise_rms=0.,phase_rms_rad=0.)
        core.process(np.full(32,.2));reference=copy.deepcopy(core);double=copy.deepcopy(core)
        actual=chip._rf_step(core,[.2])
        scale=1+(chip.shared_rail.voltage/chip.shared_rail.nominal-1)*chip.shared_rail.rf_gain_fraction
        assert np.array_equal(actual,reference.process([.2],supply_scale=scale,supply_phase_rad=phase))
        assert np.array_equal(core.rx.state,reference.rx.state)
        double.process([.2],supply_scale=scale,supply_phase_rad=phase+chip.shared_rail.phase)
        assert not np.array_equal(core.rx.state,double.rx.state)
        try:chip.lo_clock.rail_frequency(26e-9)
        except ValueError:pass
        else:raise AssertionError('LO extrapolated past known rail interval')
    active=make(6.25e-9)
    source=lambda index:complex((active.stream['tx_buffer']&255)/2048,0)
    active.attach_rf_stream(source);active.start();active.advance(2e-6)
    assert active.state=='active'
    args=dict(mode=0,source_hz=10e6,sample_bits=24,frames=5,epoch=0,tx_source=lambda i:0x155)
    assert active.transfer(**args)['fault'] is None
    clock=active.lo_clock;rail=active.shared_rail;core=active.rf_stream
    active.stop();active.advance(active.time+1e-6);active.resume_rf_stream(source);active.start();active.advance(active.time+3e-6)
    assert active.transfer(**{**args,'epoch':active.epoch})['fault'] is None
    assert active.lo_clock is clock and active.shared_rail is rail and active.rf_stream is core
    assert clock.time==rail.time==active.time
    samples=np.full(128,.2+.1j)
    lo=dict(max_step_s=6.25e-9,noise_rms_hz=100000.)
    baseline,_=live_host_rf_observation(samples,settings,lo_config=lo)
    neutral,_=live_host_rf_observation(samples,settings,lo_config=lo,
        rail_config=dict(lo_hz_per_v=0.,rf_gain_fraction=0.,inductance_h=5e-9))
    assert np.array_equal(baseline,neutral)
    return dict(expected_open_loop_phase_rad=expected,measured_phase_rad=values,
        maximum_phase_error_rad=max(abs(v-expected) for v in values),
        no_double_counted_rail_phase=True,known_horizon_enforced=True,retained_coupled_recovery=True,
        disabled_coupling_matches_baseline=True,
        scope='Exact RC held-oscillator phase reference plus a finite live recovery case. PLL uses analytic passive rail evolution between actual charge events; converter cadence remains fixed.')


def live_rf_startup_controls():
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    rows=[]
    for config,reason,state,until in ((dict(free_hz=2.7e9),'startup_window_exhausted','acquiring',20e-6),
                                    (dict(reference_hz=1e6),'reference_lost','fault',100e-9)):
        try:live_host_rf_observation(np.full(64,.2),settings,lo_config=config,
                rail_config=dict(full_host_activity=True,input_transition_charge_c=.3e-12))
        except LiveRFTransportFailure as error:report=error.report
        else:raise AssertionError('Unqualified startup admitted RF payload')
        assert report['stage']=='startup' and report['chip_state']==state
        assert report['flow']['fault']==reason and abs(report['observed_until_s']-until)<1e-18
        assert report['dac_samples']==report['flow']['produced_bits']==report['flow']['returned_bits']==0
        assert all(value==0 for value in report['flow']['tx'].values())
        assert report['shared_rail']['host_events']==report['shared_rail']['input_events']==report['shared_rail']['converter_events']==0
        assert report['lo_clock']['first_lock_s'] is None and not report['lo_clock']['locked']
        json.dumps(report,allow_nan=False)
        rows.append(dict(configuration=config,report=report))
    observed,report=live_host_rf_observation(np.full(64,.2),settings,lo_config=dict(max_step_s=6.25e-9))
    assert len(observed)==64 and report['stage']=='transport' and report['flow']['fault'] is None
    return dict(cases=rows,nominal_startup_delivers=True,
        scope='Bounded external-fixture observation window, not a new on-chip watchdog. Untunable LO remains acquiring; reference absence under the declared 100 ns monitor faults. Neither path prefills queues or starts conversions, and neither fabricates a reset.')


def fractional_divider_phase_screen():
    """Linear sampled-loop sensitivity to actual integer-divider sequences.

    Nominal-edge forcing only; not feedback-edge/PFD or RF payload closure.
    """
    from shaped_fractional_pll import SecondOrderSequence
    results=[]
    for carrier in (2400000000,2412000000,2437000000):
     ratio=Fraction(carrier,40000000);seq=SecondOrderSequence(ratio);seen={};errors=[];counts=[]
     while True:
      state=(seq.accumulator,seq.second,seq.previous_carry)
      if state in seen:
       start=seen[state];errors=errors[start:];counts=counts[start:];break
      seen[state]=len(errors);counts.append(seq.step());errors.append(float(Fraction(seq.total)-seq.emitted*ratio)/float(ratio))
      assert len(errors)<10000
     forcing=np.array(errors);forcing-=forcing.mean();n=len(forcing)
     for bandwidth in (.3e6,1e6,2.5e6):
      clock=ReferenceDrivenLO([0.,25e-9],divider=float(ratio),bandwidth_hz=bandwidth)
      t=1/clock.reference_hz;g=clock.kvco/clock.divider
      matrix=np.array([[1-g*(clock.kp*t+.5*clock.ki*t*t),-g*t],[clock.ki*t,1.]])
      drive=np.array([-g*(clock.kp*t+.5*clock.ki*t*t),clock.ki*t])
      # Exact periodic solution for this linear held-detector model.
      state=np.zeros(2)
      for value in forcing:state=matrix@state+drive*value
      state=np.linalg.solve(np.eye(2)-np.linalg.matrix_power(matrix,n),state);initial=state.copy();trace=[]
      for value in forcing:trace.append(state[0]);state=matrix@state+drive*value
      assert np.max(abs(state-initial))<1e-10
      spectrum=np.fft.fft(forcing);predicted=[]
      for k,value in enumerate(spectrum):
       z=np.exp(2j*np.pi*k/n);predicted.append(np.linalg.solve(z*np.eye(2)-matrix,drive)[0]*value)
      assert np.max(abs(np.fft.ifft(predicted).real-trace))<1e-10
      phase=-2*np.pi*float(ratio)*np.array(trace)
      row=dict(carrier_hz=carrier,bandwidth_hz=bandwidth,period=n,integer_counts=sorted(set(counts)),phase_rms_rad=float(np.sqrt(np.mean(phase**2))),phase_only_evm=float(np.sqrt(np.mean(abs(np.exp(1j*phase)-1)**2))))
      results.append(row)
    return dict(cases=results,periodic_and_fourier_agree=True,rf_payload_qualification=False,scope='Mean-removed cumulative integer-divider error mapped to nominal reference phase; linear held-detector loop. No actual feedback-edge/PFD timing, detector nonlinearity, oscillator/rail noise, retune or RF observer.')


def lo_reference_phase_controls():
    """Independent steady transfer bounds versus live held-detector PLL."""
    from oscillator_noise import FrequencyNoise
    rows=[]
    for bandwidth in (1e6,1.5e6,2e6,2.5e6,3e6):
        base=ReferenceDrivenLO([0.,25e-9],bandwidth_hz=bandwidth)
        period=1/base.reference_hz;gain=base.kvco/base.divider
        matrix=np.array([[1-gain*(base.kp*period+.5*base.ki*period**2),-gain*period],
                         [base.ki*period,1.]])
        forcing=np.array([-gain*(base.kp*period+.5*base.ki*period**2),base.ki*period])
        assert max(abs(np.linalg.eigvals(matrix)))<1
        oscillator=[];reference=[];bound=0.;reference_phase_power=0.
        for frequency in np.arange(1,9)*250e3:
            omega=2*np.pi*frequency;z=np.exp(1j*omega*period)
            transfer=np.linalg.solve(z*np.eye(2)-matrix,forcing)
            amplitude=base.reference_hz*.5e-12  # Eight tones: 1 ps RMS equivalent.
            ref_frequency=(z-1)*(transfer[0]+1)*amplitude/period
            osc_state=np.linalg.solve(z*np.eye(2)-matrix,[-50000*(z-1)/(1j*omega*base.divider),0j])
            osc_frequency=(z-1)*osc_state[0]/period
            bound+=abs(ref_frequency)+abs(osc_frequency)
            reference_phase_power+=abs(2*np.pi*base.divider*transfer[0]*amplitude)**2/2
            reference.append((float(frequency),amplitude,float(-np.angle(ref_frequency)-omega*(22e-6-period))))
            oscillator.append((float(frequency),50000.,float(-np.angle(osc_frequency)-omega*(22e-6-period))))
        clock=ReferenceDrivenLO([i/40e6 for i in range(1001)],bandwidth_hz=bandwidth,
            detector_phase_tones=reference,max_step_s=6.25e-9)
        clock.set_noise(0.,FrequencyNoise(oscillator));clock.advance(20e-6)
        measured=[];qualified=[]
        for index in range(801,961):
            clock.advance(index/40e6);measured.append(clock.last_frequency_error);qualified.append(clock.locked)
        assert abs(max(measured)-bound)<1e-5
        if bandwidth<2e6:assert not all(qualified)
        else:assert all(qualified)
        # Solver subdivision cannot redraw or shift detector noise.
        split=ReferenceDrivenLO([i/40e6 for i in range(1001)],bandwidth_hz=bandwidth,
            detector_phase_tones=reference,max_step_s=6.25e-9)
        split.set_noise(0.,FrequencyNoise(oscillator))
        for time in (7.123e-6,16.789e-6,24e-6):split.advance(time)
        assert abs(split.error-clock.error)<1e-12 and abs(split.integral-clock.integral)<1e-12
        rows.append(dict(bandwidth_hz=bandwidth,combined_frequency_bound_hz=float(bound),
            measured_peak_hz=max(measured),all_observations_qualified=all(qualified),
            reference_output_phase_rms_rad=float(math.sqrt(reference_phase_power)),
            detector_phase_tones=reference,oscillator_noise_tones=oscillator))
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    fs=settings['sample_hz'];known=diagnostic_chirp_prefix(fs,406250.)
    wave=gfsk(np.random.default_rng(951).integers(0,2,64),fs=fs)
    samples=np.r_[np.zeros(73),known,np.zeros(128),.2*wave.samples,np.zeros(128)]
    coupled=[];candidate=next(row for row in rows if row['bandwidth_hz']==2e6)
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    for staged,coupling in ((False,.1),(False,.25),(True,.05),(True,.075),(True,.1),(True,.25)):
        config=dict(bandwidth_hz=2e6,max_step_s=6.25e-9,
            noise_tones=candidate['oscillator_noise_tones'],detector_phase_tones=candidate['detector_phase_tones'])
        rail=dict(full_host_activity=True,input_transition_charge_c=.3e-12,
            host_coupling=coupling,inductance_h=5e-9)
        transport_options={}
        if staged:
            rail.update(block_write_cap_f=caps['wr_clk'],block_read_cap_f=caps['rd_clk'],block_clock_coupling=1.)
            transport_options=dict(host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
                converter_clock_config=dict(jitter_amplitude_s=.5e-9))
        try:
            observed,transport=live_host_rf_observation(samples,settings,host_mode=0,
                transport_allocation='exclusive',lo_config=config,rail_config=rail,**transport_options,**declared_rf_noise(.2,12))
        except LiveRFTransportFailure as error:
            coupled.append(dict(staged_host=staged,host_coupling=coupling,fault=error.report['flow']['fault'],quality_pass=False,transport=error.report))
            continue
        _,coarse=acquire_live_prefix(observed,known,fs)
        corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
        at=acquisition['start']+len(known)+128+np.arange(len(wave.samples))
        recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
        evm=float(np.linalg.norm(recovered-.2*wave.samples)/np.linalg.norm(.2*wave.samples))
        errors=int(np.count_nonzero(decisions(wave,recovered)!=wave.symbols))
        if staged:
            load=transport['shared_rail'];cdc=transport['flow']['host_staging']['cdc']
            assert load['block_write_edges']==cdc['write_edges'] and load['block_read_edges']==cdc['read_edges']
            charge=(cdc['write_edges']*caps['wr_clk']+cdc['read_edges']*caps['rd_clk'])*3.3
            assert math.isclose(load['block_clock_charge_c'],charge,rel_tol=1e-11)
        coupled.append(dict(staged_host=staged,host_coupling=coupling,fault=None,evm_rms=evm,
            symbol_errors=errors,quality_pass=evm<=.1 and errors==0))
    # Corrected noise changes returned host bits and therefore rail switching.
    # Retain the resulting charged-host failure; do not call the .1 envelope closed.
    assert all(row['fault']=='lo_unqualified' for row in coupled if row['host_coupling']==.25)
    assert any(row['staged_host'] and row['host_coupling']==.1 and row['fault']=='lo_unqualified' for row in coupled)
    assert any(not row['staged_host'] and row['host_coupling']==.1 and row['quality_pass'] for row in coupled)
    return dict(cases=rows,coupled_rf=coupled,split_equivalent=True,
        candidate_operating_envelope_pass=all(row['quality_pass'] for row in coupled if row['host_coupling']==.1),
        scope='Steady unsaturated 40 MHz nominal-grid reference, 100 kHz RMS oscillator noise and 1 ps RMS equivalent additive detector phase. Independent phases aligned to frequency worst case. Detector disturbance feeds control and qualification while physical oscillator phase remains separately integrated. Coupled 64-bit GFSK controls include complete host activity and shared RLC rail at two coupling values, comparing scalar staging with charged block CDC and prescribed paired converter jitter. Not displaced reference edges, independent converter noise, physical phase-noise evidence or a continuous RF operating envelope.')


def lo_noise_envelope_controls():
    """Steady linear sampled-loop bound, independently exercised in live RF."""
    from oscillator_noise import FrequencyNoise
    clock=ReferenceDrivenLO([i/40e6 for i in range(4001)])
    period=1/clock.reference_hz;gain=clock.kvco/clock.divider
    matrix=np.array([[1-gain*(clock.kp*period+.5*clock.ki*period**2),-gain*period],
                     [clock.ki*period,1.]])
    assert max(abs(np.linalg.eigvals(matrix)))<1
    contributions=[];tones=[];phase_bound=0.;control_bounds=[0.,0.]
    target=22e-6
    for frequency in np.arange(1,9)*250e3:
        amplitude=50000.;z=np.exp(2j*np.pi*frequency*period)
        forcing=np.array([-amplitude*(z-1)/(2j*np.pi*frequency*clock.divider),0j])
        state=np.linalg.solve(z*np.eye(2)-matrix,forcing)
        observed_frequency=(z-1)*state[0]/period
        contributions.append(float(abs(observed_frequency)));phase_bound+=abs(state[0])
        control_bounds[0]+=abs(clock.kp*state[0]+state[1])
        control_bounds[1]+=abs((clock.kp+clock.ki*period)*state[0]+state[1])
        angle=-np.angle(observed_frequency)-2*np.pi*frequency*(target-period)
        tones.append((float(frequency),amplitude,float(angle)))
    bound=sum(contributions);bias=(clock.reference_hz*clock.divider-clock.free_hz)/clock.kvco
    assert phase_bound<clock.lock_phase_cycles and abs(bias)+max(control_bounds)<clock.rail
    clock.set_noise(0.,FrequencyNoise(tones));clock.advance(20e-6)
    measured=[]
    for index in range(801,961):
        clock.advance(index/40e6);measured.append(clock.last_frequency_error)
    assert abs(max(measured)-bound)<1e-5
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    try:
        live_host_rf_observation(np.full(256,.2+.1j),settings,
            lo_config=dict(noise_tones=tones,max_step_s=6.25e-9),
            rail_config=dict(full_host_activity=True,input_transition_charge_c=.3e-12,
                             lo_hz_per_v=0.,rf_gain_fraction=0.))
    except LiveRFTransportFailure as error:
        report=error.report
    else:raise AssertionError('Worst-phase spectral noise admitted continuous traffic')
    assert report['flow']['fault']=='lo_unqualified'
    return dict(spectrum_rms_hz=100000.,tone_frequencies_hz=[row[0] for row in tones],
        per_tone_observed_frequency_amplitude_hz=contributions,worst_phase_bound_hz=bound,
        measured_peak_hz=max(measured),frequency_limit_hz=clock.lock_frequency_hz,
        strict_rms_ceiling_without_supply_hz=100000.*clock.lock_frequency_hz/bound,
        detector_phase_bound_cycles=float(phase_bound),control_peak_bound_v=float(abs(bias)+max(control_bounds)),
        live_failure=report,
        scope='Steady, unsaturated nominal-reference loop; fixed eight-tone amplitudes with arbitrary phases. Matrix response and time-domain/live checks agree. Bound excludes startup, supply pulling, reference jitter and detector error; it is not a physical noise specification or a selected reduced-noise assumption.')


def external_receive_payload(*,lo_configuration=None):
    """Independent remote timing; observer only receives samples and prefix."""
    fs=10e6
    settings=dict(sample_hz=fs,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,
                  rx_filter_order=5,converter_bits=12)
    known=diagnostic_chirp_prefix(fs,406250.)
    wave=gfsk(np.random.default_rng(953).integers(0,2,1024),fs=fs)
    samples=np.r_[np.zeros(73),known,np.zeros(128),.2*wave.samples,np.zeros(256)]
    timeline=np.arange(len(samples));rows=[]
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    for ppm,step_ppm in ((0.,0.),(-100.,0.),(100.,0.),(300.,0.),(0.,2000.)):
        def source(t):
            elapsed=(t-37e-9)*fs
            step_at=73+len(known)+128+600*10
            at=elapsed*(1+ppm*1e-6)+np.maximum(elapsed-step_at,0)*step_ppm*1e-6
            return (np.interp(at,timeline,samples.real,left=0,right=0)
                    +1j*np.interp(at,timeline,samples.imag,left=0,right=0))
        observed,transport=live_host_rf_observation(np.zeros(len(samples)),settings,
            host_mode=0,transport_allocation='exclusive',receive_source=source,
            host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
            offset_hz=48000.,converter_clock_config=dict(jitter_amplitude_s=.5e-9),
            lo_config=(dict(max_step_s=6.25e-9,noise_rms_hz=100000.,noise_seed=830) if lo_configuration is None else lo_configuration),
            rail_config=dict(host_coupling=.1,inductance_h=5e-9,
                full_host_activity=True,input_transition_charge_c=.3e-12,block_write_cap_f=caps['wr_clk'],
                block_read_cap_f=caps['rd_clk'],block_clock_coupling=1.),
            **declared_rf_noise(.2,12))
        _,coarse=acquire_live_prefix(observed,known,fs)
        corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
        # Ground-truth payload appears only in scoring, not acquisition.
        at=acquisition['start']+len(known)+128+np.arange(len(wave.samples))
        recovered=(np.interp(at,np.arange(len(corrected)),corrected.real)
                   +1j*np.interp(at,np.arange(len(corrected)),corrected.imag))
        evm=float(np.linalg.norm(recovered-.2*wave.samples)/np.linalg.norm(.2*wave.samples))
        errors=int(np.count_nonzero(decisions(wave,recovered)!=wave.symbols))
        passed=errors==0 and evm<=.1
        # Prefix-only fitting is a diagnostic, not the delivery gate. Corrected
        # noise can invalidate an old near-threshold constant-rate result.
        if ppm==300. or step_ppm:assert not passed
        tracked,fit=decision_directed_gfsk_timing(observed,known)
        holdout=520*10
        heldout_evm=float(np.linalg.norm(tracked[holdout:]-.2*wave.samples[holdout:])/np.linalg.norm(.2*wave.samples[holdout:]))
        heldout_errors=int(np.count_nonzero(decisions(wave,tracked)[520:]!=wave.symbols[520:]))
        if step_ppm==0.:assert heldout_evm<=.1 and heldout_errors==0
        else:assert heldout_evm>.1
        quality=gfsk_decision_quality(tracked)
        assert quality['packet_quality_pass']==(step_ppm==0.)
        assert quality['candidate_payload_bits']==(wave.symbols.tolist() if step_ppm==0. else [])
        changed=observed.copy();changed[len(known)+128+5200+128:]=0
        altered,other=decision_directed_gfsk_timing(changed,known)
        assert other==fit and np.array_equal(altered[:5120],tracked[:5120])
        rows.append(dict(remote_clock_ppm=ppm,clock_step_ppm=step_ppm,clock_step_after_bit=600,launch_offset_s=37e-9,
            evm_rms=evm,symbol_errors=errors,quality_budget=.1,
            conditional_quality_pass=passed,acquisition=acquisition,transport=transport,
            decision_fit=fit,receiver_quality=quality,heldout_evm_rms=heldout_evm,heldout_bit_errors=heldout_errors,
            corrected_quality_pass=heldout_evm<=.1 and heldout_errors==0 and quality['packet_quality_pass'],holdout_does_not_affect_fit=True))
        if ppm==300.:
            damaged=observed.copy();damaged[10000:]=0
            output,_=decision_directed_gfsk_timing(damaged,known)
            check=gfsk_decision_quality(output)
            assert not check['packet_quality_pass'] and not check['candidate_payload_bits']
            rows[-1]['tail_erasure_control']=check
            rejections=[]
            for label,bad in (('truncated',observed[:8000]),
                              ('fit_erasure',np.r_[observed[:5000],np.zeros(2000),observed[7000:]]),
                              ('silence',np.zeros_like(observed))):
                try:decision_directed_gfsk_timing(bad,known)
                except ValueError as error:rejections.append(dict(case=label,reason=str(error)))
                else:raise AssertionError('Invalid GFSK receiver input admitted')
            rows[-1]['rejection_controls']=rejections

    return dict(cases=rows,payload_bits=1024,lo_configuration=lo_configuration,prefix_only_not_acceptance_gate=True,
        scope='Normalized independent remote envelope with linear interpolation; local TX zeros. Diagnostic prefix only, finite noise seed and load. Prefix-only +300ppm failure retained; receiver-derived affine correction passes held-out bits. Live charged CDC/PLL, finite constant-rate cases; receiver-derived quality flag gates payload and rejects a tail erasure and a late clock-rate step; broader corruption controls, streaming tracking and standard packet acquisition remain open.')


def connected_lo_payload(transport_allocation='exclusive',case_labels=None):
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    fs=settings['sample_hz'];known=diagnostic_chirp_prefix(fs,406250.)
    rows=[]
    cases=[('noise_'+str(noise),noise,None) for noise in (0.,100000.,200000.)]
    cases += [('rail_'+str(coupling),100000.,dict(host_coupling=coupling,inductance_h=5e-9)) for coupling in (.1,1.)]
    cases += [('rail_quiet_1.0',0.,dict(host_coupling=1.,inductance_h=5e-9))]
    cases += [(label,100000.,dict(host_coupling=1.,inductance_h=5e-9)) for label in ('rail_bw_0.5M','rail_bw_2M')]
    cases += [('rail_'+str(coupling),100000.,dict(host_coupling=coupling,inductance_h=5e-9)) for coupling in (.25,.5)]
    cases += [('rail_sensitivity_'+str(sensitivity),100000.,dict(host_coupling=1.,inductance_h=5e-9,lo_hz_per_v=sensitivity)) for sensitivity in (5e6,0.)]
    cases += [('complete_host_'+str(charge),100000.,dict(host_coupling=.1,inductance_h=5e-9,
        full_host_activity=True,input_transition_charge_c=charge)) for charge in (0.,.3e-12,3e-12)]
    cases += [('allocation_complete_'+str(charge),100000.,dict(host_coupling=.25,inductance_h=5e-9,
        full_host_activity=True,host_clock_phase=None,input_transition_charge_c=charge)) for charge in (0.,.3e-12)]
    cases += [('allocation_quiet',0.,dict(host_coupling=.25,inductance_h=5e-9,
        full_host_activity=True,host_clock_phase=None,input_transition_charge_c=.3e-12)),
              ('allocation_no_pulling',100000.,dict(host_coupling=.25,inductance_h=5e-9,
        full_host_activity=True,host_clock_phase=None,input_transition_charge_c=.3e-12,lo_hz_per_v=0.))]
    cases += [(f'clock_edges_{coupling}_{phase}',100000.,dict(host_coupling=coupling,inductance_h=5e-9,
        full_host_activity=True,input_transition_charge_c=.3e-12,host_clock_phase=phase))
        for coupling in (.1,.25) for phase in (0,1)]
    variants={f'long_{noise_seed}_{payload_seed}':dict(noise_seed=noise_seed,payload_seed=payload_seed,symbols=256,offset_hz=0.)
              for noise_seed in (830,831) for payload_seed in (951,952)}
    variants.update({f'offset_{int(offset)}_832':dict(noise_seed=832,payload_seed=953,symbols=1024,offset_hz=offset)
                     for offset in (-48000.,48000.)})
    variants.update({f'packet_offset_{int(offset)}_830':dict(noise_seed=830,payload_seed=953,symbols=1024,offset_hz=offset)
                     for offset in (-48000.,0.,48000.)})
    variants.update({f'timed_offset_{int(offset)}':dict(noise_seed=830,payload_seed=953,symbols=1024,
        offset_hz=offset,converter_clock_config=dict(jitter_amplitude_s=.5e-9)) for offset in (-48000.,0.,48000.)})
    variants['timed_zero_jitter']=dict(noise_seed=830,payload_seed=953,symbols=1024,offset_hz=0.,converter_clock_config={})
    variants['timed_block_host']=dict(noise_seed=830,payload_seed=953,symbols=1024,offset_hz=0.,converter_clock_config=dict(jitter_amplitude_s=.5e-9),host_block_words=8)
    variants['timed_cdc_host']=dict(variants['timed_block_host'],host_cdc_read_hz=40e6,host_cdc_phase=.37)
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    for coupling in (0.,.1,1.):
        variants['cdc_charge_'+str(coupling)]=dict(variants['timed_cdc_host'],block_clock_coupling=coupling)
    for label,variant in variants.items():
        rail=dict(host_coupling=.1,inductance_h=5e-9,full_host_activity=True,input_transition_charge_c=.3e-12)
        if 'block_clock_coupling' in variant:
            rail.update(block_write_cap_f=caps['wr_clk'],block_read_cap_f=caps['rd_clk'],block_clock_coupling=variant['block_clock_coupling'])
        cases.append((label,100000.,rail))
    if case_labels is not None:
        if not case_labels or set(case_labels)-{row[0] for row in cases}:raise ValueError('Unknown or empty LO case selection')
        cases=[row for row in cases if row[0] in case_labels]
    for label,noise,rail_config in cases:
        variant=variants.get(label,dict(noise_seed=830,payload_seed=951,symbols=64,offset_hz=0.))
        wave=gfsk(np.random.default_rng(variant['payload_seed']).integers(0,2,variant['symbols']),fs=fs)
        samples=np.r_[np.zeros(73),known,np.zeros(128),.2*wave.samples,np.zeros(128)]
        bandwidth={'rail_bw_0.5M':.5e6,'rail_bw_2M':2e6}.get(label,1e6)
        config=dict(max_step_s=6.25e-9,noise_rms_hz=noise,noise_seed=variant['noise_seed'],bandwidth_hz=bandwidth)
        try:observed,transport=live_host_rf_observation(samples,settings,host_mode=0,transport_allocation=transport_allocation,offset_hz=variant['offset_hz'],lo_config=config,rail_config=rail_config,converter_clock_config=variant.get('converter_clock_config'),host_block_words=variant.get('host_block_words',1),host_cdc_read_hz=variant.get('host_cdc_read_hz'),host_cdc_phase=variant.get('host_cdc_phase',0.),**declared_rf_noise(.2,12))
        except LiveRFTransportFailure as error:
            rows.append(dict(comparison=label,stimulus=variant,source_samples=len(samples),noise_rms_hz=noise,lo_configuration=config,rail_configuration=rail_config,transport=error.report,conditional_quality_pass=False));continue
        row=dict(comparison=label,stimulus=variant,source_samples=len(samples),noise_rms_hz=noise,lo_configuration=config,rail_configuration=rail_config,transport=transport,quality_budget=.1)
        try:
            _,coarse=acquire_live_prefix(observed,known,fs)
            corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
        except ValueError as error:
            rows.append(dict(row,acquired=False,reason=str(error),conditional_quality_pass=False));continue
        at=acquisition['start']+len(known)+128+np.arange(len(wave.samples))
        recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
        evm=float(np.linalg.norm(recovered-.2*wave.samples)/np.linalg.norm(.2*wave.samples))
        errors=int(np.count_nonzero(decisions(wave,recovered)!=wave.symbols))
        rows.append(dict(row,acquired=True,acquisition=acquisition,evm_rms=evm,symbol_errors=errors,conditional_quality_pass=errors==0 and evm<=.1))
        if label.startswith('cdc_charge_'):
            rail=transport['shared_rail'];flow=transport['flow']['host_staging']['cdc']
            assert rail['block_write_edges']==flow['write_edges'] and rail['block_read_edges']==flow['read_edges']
            expected=(rail['block_write_edges']*caps['wr_clk']+rail['block_read_edges']*caps['rd_clk'])*3.3*variant['block_clock_coupling']
            assert math.isclose(rail['block_clock_charge_c'],expected,rel_tol=1e-11,abs_tol=1e-25)
        if label in ('noise_100000.0','rail_0.1','complete_host_3e-13','packet_offset_0_830','timed_offset_0','timed_block_host','timed_cdc_host','cdc_charge_1.0'):
            cut=transport['frames']//2 if label in ('packet_offset_0_830','timed_offset_0','timed_block_host','timed_cdc_host','cdc_charge_1.0') else 7
            split,report=live_host_rf_observation(samples,settings,host_mode=0,transport_allocation=transport_allocation,offset_hz=variant['offset_hz'],lo_config=config,rail_config=rail_config,converter_clock_config=variant.get('converter_clock_config'),host_block_words=variant.get('host_block_words',1),host_cdc_read_hz=variant.get('host_cdc_read_hz'),host_cdc_phase=variant.get('host_cdc_phase',0.),chunks=(cut,transport['frames']-cut),**declared_rf_noise(.2,12))
            assert np.array_equal(observed,split) and report==transport
            rows[-1]['chunk_split_frame']=cut
    if case_labels is None:
        assert rows[0]['conditional_quality_pass']
        assert rows[1]['conditional_quality_pass'] and rows[1]['evm_rms']>rows[0]['evm_rms']
        assert rows[2]['transport']['flow']['fault']=='lo_unqualified'
        assert rows[3]['conditional_quality_pass'] and rows[4]['transport']['flow']['fault']=='lo_unqualified'
        by_name={row['comparison']:row for row in rows}
        assert all(by_name[name]['transport']['dac_samples']<73 for name in ('rail_1.0','rail_bw_0.5M','rail_bw_2M'))
        assert by_name['rail_0.25']['transport']['flow']['fault']=='lo_unqualified'
        failed=by_name['rail_0.25']
        # Data-dependent rail timing changes with noise placement. Require an
        # observed clock fault before completion, not a historical sample index.
        assert failed['transport']['dac_samples']<failed['source_samples']
        assert failed['transport']['lo_clock']['last_lock_loss']['time_s']==failed['transport']['observed_until_s']
        assert by_name['rail_sensitivity_0.0']['conditional_quality_pass']
        assert by_name['complete_host_0.0']['conditional_quality_pass'] and by_name['complete_host_3e-13']['conditional_quality_pass']
        assert by_name['complete_host_3e-12']['transport']['flow']['fault']=='lo_unqualified'
        assert all(by_name[name]['conditional_quality_pass'] for name in variants if name.startswith('long_'))
        assert all(by_name[name]['transport']['flow']['fault']=='lo_unqualified' for name in variants if name.startswith('offset_'))
        assert all(by_name[name]['conditional_quality_pass'] for name in variants if name.startswith(('packet_offset_','timed_')))
        assert by_name['timed_offset_0']['chunk_split_frame']>7
        assert all(by_name['cdc_charge_'+str(c)]['conditional_quality_pass'] for c in (0.,.1,1.))
        for phase in (0,1):
            assert by_name[f'clock_edges_0.1_{phase}']['conditional_quality_pass']
            assert by_name[f'clock_edges_0.25_{phase}']['transport']['flow']['fault']=='lo_unqualified'
    return dict(transport_allocation=transport_allocation,case_selection=case_labels,cases=rows,chunk_invariant=True,scope='LO residual phase rotates the received RF envelope against an ideal remote carrier. Rail cases drive this same PLL from live charge-event RLC trajectories, without adding direct rail phase twice. Existing additive/IID phase budget remains present. Finite spectral noise realization, independent trained observer; timed variants use prescribed paired DAC/ADC jitter and other cases retain fixed converter cadence; not a physical envelope or common-LO cancellation model.')


def host_clock_edge_controls():
    rows=[]
    for phase in (None,0,1):
        rail=SharedRail(host_clock_phase=phase)
        charge=rail.host_cap*rail.nominal*rail.host_coupling
        pulses=[]
        for index in range(7):
            when=index*4e-9;rail.advance(when)
            rise=.5 if phase is None else int(index%2==phase)
            pulses.append((when,charge*rise));rail.host_word(0)
            expected=sum(q/rail.c*math.exp(-(when-t)/(rail.r*rail.c)) for t,q in pulses)
            assert math.isclose(rail.droop,expected,rel_tol=1e-12,abs_tol=1e-18)
            assert math.isclose(rail.charge,sum(q for _,q in pulses),rel_tol=1e-12,abs_tol=1e-25)
        assert rail.host_clock_rises==(3.5 if phase is None else 4-phase)
        rows.append(dict(phase=phase,rises=rail.host_clock_rises,charge_c=rail.charge,final_droop_v=rail.droop))
    for invalid in (-1,2,True,.5):
        try:SharedRail(host_clock_phase=invalid)
        except ValueError:pass
        else:raise AssertionError('Invalid clock edge phase accepted')
    # Same charge per two words, different intermediate state; averaging must
    # not be confused with the actual edge sequence.
    for phase in (0,1):
        edge=SharedRail(host_clock_phase=phase);average=SharedRail()
        for index in range(64):
            edge.advance(index*4e-9);average.advance(index*4e-9)
            edge.host_word(0);average.host_word(0)
        assert math.isclose(edge.charge,average.charge,rel_tol=1e-12)
        assert abs(edge.voltage-average.voltage)>1e-4
    assert SharedRail(full_host_activity=True).host_clock_phase==0
    assert SharedRail(full_host_activity=True,host_clock_phase=None).host_clock_phase is None
    assert SharedRail().host_clock_phase is None
    return dict(cases=rows,analytic_rc_pulse_sum=True,odd_event_counts=True,equal_even_count_charge_different_trajectory=True,
        scope='Ideal instantaneous charge at alternating forwarded DDR rising edges, either initial phase; finite edge shape, stopped-clock policy and physical clock driver remain unqualified.')


def allocation_load_controls(exclusive=None):
    """Matched schedule/load completeness controls with unchanged clock budget."""
    labels=['rail_0.25','allocation_complete_0.0','allocation_complete_3e-13','allocation_quiet','allocation_no_pulling']
    if exclusive is None:exclusive=connected_lo_payload(case_labels=labels)
    legacy=connected_lo_payload(transport_allocation='legacy',case_labels=labels)
    rows=[]
    for result in (legacy,exclusive):
        for row in result['cases']:
            if row['comparison'] not in labels:continue
            report=row['transport'];rail=report['shared_rail'];clock=report['lo_clock']
            rows.append(dict(allocation=result['transport_allocation'],comparison=row['comparison'],noise_rms_hz=row['noise_rms_hz'],
                rail_configuration=row['rail_configuration'],dac_samples=report['dac_samples'],
                fault=report['flow']['fault'],evm_rms=row.get('evm_rms'),conditional_quality_pass=row['conditional_quality_pass'],
                minimum_v=rail['minimum_v'],charge_c=rail['injected_charge_c'],
                last_frequency_error_hz=clock['last_frequency_error_hz'],elapsed_s=report['flow']['simulated_s']))
    assert len(rows)==2*len(labels)
    for row in rows:
        if row['comparison'] in ('allocation_quiet','allocation_no_pulling'):assert row['conditional_quality_pass']
        else:assert row['fault']=='lo_unqualified' and row['minimum_v']>2.5
    return dict(cases=rows,scope='Same GFSK/LO seed and 0.25 coupling; this matched matrix explicitly retains averaged clock charge. Compare legacy/exclusive slots with partial activity, complete D2H, and complete D2H plus local H2D charge. Zero intrinsic frequency noise and zero supply pulling are labeled counterfactuals, not adopted targets. No lock/quality budget changes; feedback makes this a closed-loop intervention, not additive charge attribution.')


def reference_presence_controls():
    """Missing reference pulses interrupt live RF/host state without resetting it."""
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    edges=[i*25e-9 for i in range(4001) if not 881<=i<1280]
    def make():
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_reference(edges);chip.attach_shared_rail()
        source=lambda index:complex((chip.stream['tx_buffer']&255)/2048,0)
        chip.attach_rf_stream(source,offset_hz=48000.)
        chip.start();chip.advance(20e-6)
        assert chip.state=='active'
        return chip,source
    args=dict(mode=0,source_hz=10e6,sample_bits=24,epoch=0,tx_source=lambda index:0x155)
    whole,source=make();split,_=make()
    result=whole.transfer(frames=25,**args)
    assert split.transfer(frames=5,**args)['fault'] is None
    divided=split.transfer(frames=20,**args)
    assert result==divided and result['fault']=='reference_lost'
    assert abs(whole.time-22.1e-6)<1e-18 and whole.time==split.time
    core=whole.rf_stream;old=whole.rf_source;count=core.index
    assert core.index==split.rf_stream.index and core.index>0
    assert np.array_equal(core.rx.state,split.rf_stream.rx.state)
    assert whole.shared_rail.report()==split.shared_rail.report()
    assert result['produced_bits']==24*count and result['tx']['consumed_bits']==24*count
    assert whole.state=='fault' and whole.ready_at==math.inf
    try:whole.transfer(frames=1,**args)
    except ValueError:pass
    else:raise AssertionError('Reference fault permitted continued traffic')
    try:old(count)
    except ValueError:pass
    else:raise AssertionError('Reference fault permitted stale RF work')
    discarded=whole.stop();assert whole.parked_rf is core and core.index==count
    whole.advance(33e-6);idle_count=core.index
    assert idle_count>count
    whole.resume_rf_stream(source);whole.start();whole.advance(whole.ready_at)
    resumed=whole.transfer(frames=5,**{**args,'epoch':whole.epoch})
    assert resumed['fault'] is None and whole.rf_stream is core and core.index>idle_count

    # No future edge can satisfy a short startup guard. A gap hidden inside a
    # single long advance still faults before returning reference pulses.
    absent=BehavioralChip(Assumptions(startup_s=0.));absent.configure_numeric(engine='rf',rf=settings)
    absent.attach_reference([1e-6,1.025e-6,1.05e-6,1.075e-6]);absent.start();absent.advance(0.)
    assert absent.state=='acquiring'
    try:absent.advance(2e-6)
    except ReferenceLossError:pass
    else:raise AssertionError('Future returning edges concealed reference loss')
    assert absent.state=='fault' and abs(absent.time-100e-9)<1e-20
    monitor=ReferencePresence([0.,100e-9,200e-9,300e-9])
    assert monitor.fault_between(0.,300e-9) is None and monitor.qualified(300e-9)
    assert abs(monitor.fault_between(300e-9,500e-9)-400e-9)<1e-20
    # The check must also cover the interval between the final event and frame end.
    boundary=BehavioralChip(Assumptions(startup_s=0.));boundary.configure_numeric(engine='rf',rf=settings)
    boundary.attach_reference([0.],timeout_s=255e-9,monitor_tick_s=1e-9,required_edges=1)
    boundary.attach_rf_stream(lambda index:0j);boundary.start();boundary.advance(0.)
    final_gap=boundary.transfer(frames=1,**args)
    assert final_gap['fault']=='reference_lost' and abs(boundary.time-255e-9)<1e-20
    for candidate in (whole,split):assert candidate.reference.edges==tuple(edges)
    return dict(loss_time_s=22.1e-6,samples_before_loss=count,discarded=discarded,
        chunk_invariant=True,shared_rail_state_retained=True,rf_core_retained=True,
        recovered=True,future_edges_cannot_qualify=True,timeout_tie_accepts_edge=True,frame_end_timeout_checked=True,
        scope='Optional pulse-presence monitor on live RF/host events. Independent 10 ns monitor timer and 100 ns timeout are assumptions; PLL lock, clock pulling and standard payload acquisition remain separate requirements.')


def retained_rf_recovery():
    """Phase-preserving recovery through both host directions; same analog core."""
    import copy
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    def unpack(code):
        i=code&4095;q=(code>>12)&4095
        return ((i if i<2048 else i-4096)+1j*(q if q<2048 else q-4096))/2048
    def transport(chip,code):
        prefill=sum(code<<(24*i) for i in range(22))&((1<<512)-1)
        return chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=25,epoch=chip.epoch,
            tx_prefill_value=prefill,tx_source=lambda index:((code|(code<<24))>>((512+10*index)%24))&1023)
    results=[]
    for loss,fraction in ((loss,fraction) for loss in (False,True) for fraction in (0.,.23,.77)):
        chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
        source=lambda index:unpack(chip.stream['tx_buffer']&((1<<24)-1))
        chip.attach_rf_stream(source,offset_hz=48000.,**declared_rf_noise(.2,12))
        chip.start();chip.advance(chip.ready_at);first=transport(chip,409|(205<<12));assert first['fault'] is None
        core=chip.rf_stream;reference=copy.deepcopy(core);old=chip.rf_source;epoch=chip.epoch
        state=core.rx.state.copy();count=core.index
        discarded=chip.lose_reference() if loss else chip.stop()
        assert core.index==count and np.array_equal(core.rx.state,state) and chip.parked_rf is core
        try:chip.attach_rf_stream(source)
        except ValueError:pass
        else:raise AssertionError('Retained RF history replaced')
        chip.advance(chip.time+3e-6);chip.advance(chip.time+7e-6+fraction/10e6)
        chip.resume_rf_stream(source);chip.start();chip.advance(chip.ready_at)
        idle_samples=math.ceil(300+fraction-1e-9)
        assert core.index==count+idle_samples
        expected_phase=(1-fraction) if fraction else 0.
        assert abs(-chip.rf_idle_phase-expected_phase)<1e-7
        reference.process(np.zeros(idle_samples,complex))
        try:old(0)
        except ValueError:pass
        else:raise AssertionError('Old RF callback accepted after rearm')
        try:chip.receive(mode=0,source_hz=10e6,sample_bits=24,frames=1,epoch=epoch)
        except ValueError:pass
        else:raise AssertionError('Old host epoch accepted after rearm')
        code=205|(410<<12);flow=transport(chip,code);assert flow['fault'] is None
        expected=reference.process(np.full(64,unpack(code),complex))
        expected_bits=sum(((int(round(z.real*2048))&4095)|((int(round(z.imag*2048))&4095)<<12))<<(24*i) for i,z in enumerate(expected))
        delivered=sum(word<<(10*i) for i,word in enumerate(chip.stream['rx_words']))
        assert delivered==expected_bits&((1<<flow['returned_bits'])-1)
        assert chip.stream['rx_buffer']==expected_bits>>flow['returned_bits']
        assert chip.rf_stream is core and core.index==count+idle_samples+64 and chip.parked_rf is None
        assert abs(chip.stream['source_phase']-expected_phase)<1e-7
        results.append(dict(reference_loss=loss,restart_fraction=fraction,first_sample_delay_s=chip.stream['source_phase']/10e6,discarded=discarded,idle_and_guard_samples=idle_samples,
            resumed_samples=64,returned_bits=flow['returned_bits'],pending_bits=flow['pending_bits'],
            retained_core=True,independent_continuation_matches=True,stale_work_rejected=True))
        chip.stop()
        assert abs(chip.rf_idle_phase+expected_phase)<1e-7
        before=core.index;chip.advance(chip.time+.25/10e6)
        assert core.index==before+max(0,math.ceil(.25-expected_phase-1e-9))

    return dict(cases=results,scope='Same-setting RF resume at three host restart phases preserving converter grid, muted zero-input idle with free-running clock even after reference loss. No physical retune, stopped oscillator or full acquisition/readiness claim.')


def live_host_rf_observation(samples,settings,*,offset_hz=0.,chunks=None,source_clock_scale=1.,rail_config=None,lo_config=None,pulse_clock_config=None,converter_clock_config=None,host_mode=None,transport_allocation='legacy',host_block_words=1,host_cdc_read_hz=None,host_cdc_phase=0.,startup_ready=None,startup_deadline_s=.002,host_word_observer=None,**impairments):
    """FPGA codes through both finite host directions and persistent RF state."""
    if host_word_observer is not None and not callable(host_word_observer):
        raise ValueError('Host observer must consume emitted time/word pairs')
    if startup_ready is not None:
        if not callable(startup_ready) or not math.isfinite(startup_deadline_s) or startup_deadline_s<=0:
            raise ValueError('Bounded callable startup observer required')
        if lo_config is not None or rail_config is not None:
            raise ValueError('External startup observer has not yet been composed with shared rail or another LO')
    if pulse_clock_config is not None:
        if (rail_config is None or lo_config is not None or startup_ready is not None
                or not (converter_clock_config or {}).get('absolute_time',False)):
            raise ValueError('Pulse-clock fixture requires shared rail, absolute time and exclusive clock ownership')
    startup_wait=dict(enabled=startup_ready is not None,deadline_s=startup_deadline_s,
                      polls=0,qualified_at_s=None,transport_start_s=None)
    bits=settings['converter_bits'];width=2*bits;scale=1<<(bits-1);modulus=1<<bits;mask=modulus-1
    mode=(1 if bits==8 else 0) if host_mode is None else host_mode
    if type(mode) is not int or mode not in (0,1):raise ValueError('Unsupported host mode')
    host_hz=312.5e6 if mode else 250e6
    samples=np.asarray(samples,complex)
    if np.any(abs(samples.real)>=1) or np.any(abs(samples.imag)>=1):
        raise ValueError('Host fixture must fit signed converter range')
    codes=[int(round(z.real*scale))%modulus | ((int(round(z.imag*scale))%modulus)<<bits) for z in samples]
    stream=sum(value<<(width*i) for i,value in enumerate(codes))
    def unpack(value):
        i=value&mask;q=(value>>bits)&mask
        return ((i if i<scale else i-modulus)+1j*(q if q<scale else q-modulus))/scale
    chip=BehavioralChip(Assumptions(source_clock_scale=source_clock_scale));chip.configure_numeric(engine='rf',rf=settings)
    chip.configure_transport(transport_allocation)
    if lo_config is not None:
        ref_hz=lo_config.get('reference_hz',40e6)
        horizon=chip.a.startup_s+(len(samples)+512)/(settings['sample_hz']*source_clock_scale)+1e-6
        chip.attach_reference([i/ref_hz for i in range(math.ceil(horizon*ref_hz)+1)])
        chip.attach_lo_clock(**lo_config)
    if rail_config is not None:chip.attach_shared_rail(**rail_config)
    chip.attach_rf_stream(lambda index:unpack(chip.stream['tx_buffer']&((1<<width)-1)),offset_hz=offset_hz,**impairments)
    if pulse_clock_config is not None:
        from oscillator_noise import FrequencyNoise
        parameters=dict(pulse_clock_config)
        wait=parameters.pop('wait_for_acquisition',False)
        if type(wait) is not bool or (wait and not parameters.get('require_acquisition',False)):
            raise ValueError('Pulse startup wait requires the acquisition interlock')
        if wait and (not math.isfinite(startup_deadline_s) or startup_deadline_s<=0):
            raise ValueError('Finite positive startup deadline required')
        noise=parameters.pop('noise_rms_hz',100000.)
        seed=parameters.pop('noise_seed',831)
        pulse=RailDrivenPulsePLL(**parameters)
        pulse.set_noise(0.,FrequencyNoise.seeded(noise,seed=seed))
        chip.shared_rail.attach_pulse_clock(pulse)
        chip.attach_pulse_rf(chip.rf_stream)
        if wait:
            startup_ready=lambda at:bool(pulse.acquisition.acquired)
            startup_wait['enabled']=True
    converter_clock=None
    if converter_clock_config is not None:
        chip.attach_rf_timing(converter_clock_config);converter_clock=chip.rf_clock
        amplitude=chip.rf_clock_config['amplitude'];frequency=chip.rf_clock_config['frequency'];phase=chip.rf_clock_config['phase']
    frames=math.ceil((len(samples)+256)/(settings['sample_hz']*source_clock_scale)*host_hz/64)
    if chunks is None:chunks=(frames,)
    if sum(chunks)!=frames:raise ValueError('Chunks must cover declared observation')
    def describe(flow,stage):
        report=dict(startup_wait=dict(startup_wait),host_mode=mode,transport_allocation=chip.transport_allocation,flow=flow,frames=frames,stage=stage,chip_state=chip.state,observed_until_s=chip.time,shared_rail=chip.shared_rail.report() if chip.shared_rail is not None else None,
            dac_samples=chip.rf_stream.index,actual_sample_hz=chip.rf_stream.actual_sample_hz,
            dac_clips=chip.rf_stream.dac_clips,adc_clips=chip.rf_stream.adc_clips,
            tx_peak_open_v=(chip.rf_stream.tx_peak_open_v if chip.rf_stream.tx_port_observer is not None else None),
            receive_path='external_envelope' if chip.rf_stream.receive_source is not None else 'local_loopback',
            observation='Only samples unpacked from delivered host words')
        if converter_clock is not None:
            core=chip.rf_stream
            report['converter_clock']=dict(paired_dac_adc=True,supply_delay_coupled=False,
                reference_hz=chip.rf_clock_config['reference_hz'],reference_divider=chip.rf_clock_config['divider'],
                common_pulse_reference=bool(chip.shared_rail is not None and chip.shared_rail.pulse_clock is not None),
                absolute_time=chip.rf_clock_config['absolute_time'],
                jitter_amplitude_s=amplitude,jitter_hz=frequency,jitter_phase_rad=phase,
                committed_edges=core.index,first_sample_time_s=core.time_origin,
                first_sample_delay_s=(None if core.time_origin is None else core.time_origin-(chip.rf_clock_origin if chip.rf_clock_config['absolute_time'] else 0.)),
                minimum_interval_s=core.minimum_interval if core.index else None,
                maximum_interval_s=core.maximum_interval if core.index else None)
        if pulse_clock_config is not None:
            pulse=chip.shared_rail.pulse_clock
            report['pulse_clock']=dict(time_s=pulse.time,phase_cycles=pulse.phase,
                feedback_edges=pulse.feedback_edges,fault=pulse.fault,
                shared_supply=True,phase_history_intervals=len(pulse.phase_intervals),
                reference_disturbance_scope='PLL reference branch only; converter reference remains present',
                common_reference_loss_covered=False,
                readiness=('count interlock; phase quality not certified' if pulse.acquisition is not None else 'fixed startup guard; count/phase qualification not integrated'),
                count_acquired=None if pulse.acquisition is None else pulse.acquisition.acquired,first_acquired_s=pulse.first_acquired)
            report['shared_rail']['lo_phase_role']='Diagnostic only; mixer uses actual pulse PLL history'
        if chip.lo_clock is not None:
            clock=chip.lo_clock
            report['lo_clock']=dict(first_lock_s=clock.first_lock_time,comparisons=clock.comparisons,
                locked=clock.locked,phase_error_cycles=clock.error,integral_v=clock.integral,supply_coupled=chip.shared_rail is not None,
                last_frequency_error_hz=clock.last_frequency_error if math.isfinite(clock.last_frequency_error) else None,last_lock_loss=clock.last_lock_loss)
            if chip.shared_rail is not None:report['shared_rail']['lo_phase_role']='Open-loop diagnostic; RF uses PLL phase instead'
        return report
    chip.start()
    startup_fault=None
    try:chip.advance(chip.ready_at)
    except ReferenceLossError:startup_fault='reference_lost'
    except ClockQualificationError:startup_fault='lo_unqualified'
    except SupplyRangeError:startup_fault='shared_supply_low'
    if startup_fault is None and chip.state=='active' and startup_ready is not None:
        while True:
            if chip.time>startup_deadline_s:
                startup_fault='startup_acquisition_timeout';break
            try:qualified=startup_ready(chip.time)
            except ClockQualificationError:
                startup_fault='lo_unqualified';break
            startup_wait['polls']+=1
            if type(qualified) is not bool:raise ValueError('Startup observer must return boolean')
            if qualified:
                startup_wait['qualified_at_s']=chip.time
                # First midpoint integration interval must not precede the last
                # clock observation. Reserve a full converter period explicitly.
                chip.advance(chip.time+1/(settings['sample_hz']*source_clock_scale))
                break
            if chip.time>=startup_deadline_s:
                startup_fault='startup_acquisition_timeout';break
            next_poll=(math.floor(chip.time*40e6+1e-8)+1)/40e6
            chip.advance(min(startup_deadline_s,next_poll))
    if startup_fault is not None or chip.state!='active':
        # This fixture's observation window expired, not an invented on-chip
        # timeout/reset. No prefill, host transfer or conversion has occurred.
        flow=dict(fault=startup_fault or 'startup_window_exhausted',produced_bits=0,returned_bits=0,
            pending_bits=0,simulated_s=0.,tx=dict(prefill_bits=0,accepted_bits=0,consumed_bits=0,pending_bits=0))
        raise LiveRFTransportFailure(describe(flow,'startup'))
    startup_wait['transport_start_s']=chip.time
    args=dict(mode=mode,source_hz=settings['sample_hz'],sample_bits=width,epoch=chip.epoch,
        host_block_words=host_block_words,host_cdc_read_hz=host_cdc_read_hz,host_cdc_phase=host_cdc_phase,host_word_observer=host_word_observer,tx_prefill_value=stream&((1<<512)-1),tx_source=lambda index:(stream>>(512+10*index))&1023)
    if converter_clock is not None:args.update(chip.timed_rf_callbacks())
    for size in chunks:
        flow=chip.transfer(frames=size,**args)
        if flow['fault'] is not None:break
    report=describe(flow,'transport')
    if flow['fault'] is not None or flow['returned_bits']<len(samples)*width:
        raise LiveRFTransportFailure(report)
    returned=sum(word<<(10*i) for i,word in enumerate(chip.stream['rx_words']))
    observed=np.array([unpack((returned>>(width*i))&((1<<width)-1)) for i in range(len(samples))])
    assert flow['produced_bits']==chip.rf_stream.index*width
    assert flow['tx']['consumed_bits']==chip.rf_stream.index*width
    return observed,report


def block_clock_charge_controls():
    caps=(2.199204e-12,5.6882e-14);coupling=.25
    rail=SharedRail(block_write_cap_f=caps[0],block_read_cap_f=caps[1],block_clock_coupling=coupling)
    events=((0.,True,False),(3e-9,True,True),(8e-9,False,True))
    impulses=[]
    for at,wr,rd in events:
        rail.advance(at);rail.block_clocks(wr,rd)
        impulses.append((at,(caps[0]*wr+caps[1]*rd)*3.3*coupling))
    rail.advance(10e-9)
    expected=sum(q/1e-9*math.exp(-(10e-9-at)/(2*1e-9)) for at,q in impulses)
    assert abs(rail.droop-expected)<1e-15
    assert rail.block_edges==[2,2] and math.isclose(rail.block_charge,sum(q for _,q in impulses),rel_tol=1e-14)
    assert abs(rail.report()['charge_balance_error_c'])<1e-24
    before=rail.report()
    try:rail.block_clocks(1,False)
    except ValueError:pass
    else:raise AssertionError('Nonboolean edge accepted')
    assert rail.report()==before
    for setting in (dict(block_write_cap_f=-1.),dict(block_read_cap_f=float('nan')),dict(block_clock_coupling=1.1)):
        try:SharedRail(**setting)
        except ValueError:pass
        else:raise AssertionError('Invalid clock load accepted')
    return dict(expected_droop_v=expected,measured_droop_v=rail.droop,report=rail.report(),
        scope='Independent RC impulse sum and edge/charge accounting. Active FIFO clock pin charges only; excludes internal switching, startup/idle clock lifetime and physical rail transfer.')


def host_cdc_controls():
    def make(scale=1.):
        c=BehavioralChip(Assumptions(source_clock_scale=scale))
        c.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        c.configure_transport('exclusive');c.start();c.advance(c.ready_at)
        return c
    source=lambda i:(37*i+5)%1024
    args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=0,directions=('tx',),
              tx_source=source,host_block_words=8,host_cdc_read_hz=40e6)
    rows=[]
    for phase in (0.,.37,.99):
        whole=make();split=make();options=dict(args,host_cdc_phase=phase)
        result=whole.transfer(frames=16,**options)
        split.transfer(frames=3,**options);parts=split.transfer(frames=13,**options)
        assert result==parts and result['fault'] is None
        count=len(whole.stream['tx_samples'])
        bitstream=sum(source(i)<<(512+10*i) for i in range(count))
        expected=[(bitstream>>(10*i))&1023 for i in range(count)]
        assert whole.stream['tx_samples']==split.stream['tx_samples']==expected
        discarded=whole.stop()
        assert discarded['host_staged_bits']==result['host_staging']['pending_bits']
        rows.append(dict(phase_cycles=phase,flow=result,discarded=discarded))
    slow=make().transfer(frames=16,**dict(args,host_cdc_read_hz=31.25e6))
    assert slow['fault']=='underflow' and slow['host_staging']['cdc']['pending_bits']>0
    full=make(.01).transfer(frames=16,**dict(args,host_cdc_read_hz=1e6))
    assert full['fault']=='host_cdc_full' and full['host_staging']['cdc']['maximum_blocks']==8
    return dict(cases=rows,insufficient_block_service=slow,full_crossing=full,
        ordered_payload=True,chunk_exact=True,
        scope='Live H2D fixed-block CDC and atomic destination enqueue. Declared independent destination clock, ideal synchronizers; no physical timing, clock-power, D2H or destination gearbox implementation proof.')


def host_block_staging_controls():
    """Live queue ordering/latency; two commit stages, no implicit CDC proof."""
    def make(scale=1.):
        chip=BehavioralChip(Assumptions(source_clock_scale=scale))
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
        return chip
    source=lambda i:(i*37+5)%1024
    args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=0,
              directions=('tx',),tx_source=source,tx_prefill_bits=320,host_block_words=8)
    whole=make();split=make()
    result=whole.transfer(frames=16,**args)
    split.transfer(frames=3,**args);parts=split.transfer(frames=13,**args)
    assert result==parts and result['fault'] is None
    expected=[0]*32+[source(i) for i in range(len(whole.stream['tx_samples'])-32)]
    assert whole.stream['tx_samples']==split.stream['tx_samples']==expected
    assert result['host_staging']['pending_bits']>0
    discarded=whole.stop()
    assert discarded['host_staged_bits']==result['host_staging']['pending_bits']
    assert discarded['tx_bits']==result['tx']['pending_bits']
    scalar=make().transfer(frames=16,**dict(args,host_block_words=1,tx_prefill_bits=80))
    staged=make().transfer(frames=16,**dict(args,tx_prefill_bits=80))
    assert scalar['fault'] is None and staged['fault']=='underflow'
    assert staged['tx']['accepted_bits']==0 and staged['simulated_s']==32e-9
    # Slow consumer makes a complete block exceed available queue capacity.
    slow=make(.1);overflow=slow.transfer(frames=16,depth_bits=320,**args)
    assert overflow['fault']=='tx_overflow'
    pending=slow.stream['host_blocks'][0][1]
    assert pending and slow.stream['tx_bits']+10*len(pending)>320
    assert overflow['host_staging']['committed_bits']==overflow['tx']['accepted_bits']
    # The same staging path feeds actual timed analog conversion and host return.
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    samples=.2*np.exp(2j*np.pi*.013*np.arange(512))
    common=dict(host_mode=0,transport_allocation='exclusive',converter_clock_config={},noise_rms=0.)
    direct,_=live_host_rf_observation(samples,settings,**common)
    blocked,rf=live_host_rf_observation(samples,settings,host_block_words=8,**common)
    assert np.array_equal(direct,blocked)
    return dict(continuous=result,short_prefill=staged,atomic_overflow=overflow,
        stop_discard=discarded,chunk_exact=True,ordered_payload=True,rf_transport=rf,
        scope='H2D collection and two synchronous commit stages only. Finite three-entry pending pipe plus one collection beat; no CDC delay/metastability, D2H staging, command decoder integration or physical timing qualification.')


def exclusive_transport_controls():
    from stream_codec import Receiver,encode
    codec_cases=0
    for mode in (0,1):
        for owner in ('wire','iq'):
            for count in range(60):
                values=[(i*71+count)&1023 for i in range(count)]
                words=encode(mode,values if owner=='wire' else [],values if owner=='iq' else [],0,owner=owner)
                decoder=Receiver(mode,owner=owner);observed=[]
                for word in words:
                    event=decoder.feed(word)
                    if event is not None and event[0]==owner:observed.append(event[1])
                assert observed==values and decoder.pos==0
                codec_cases+=1
            decoder=Receiver(mode,owner=owner)
            illegal=stream_metadata(1 if owner=='iq' else 0,1 if owner=='wire' else 0,0)
            try:
                for word in illegal:decoder.feed(word)
            except ValueError:pass
            else:raise AssertionError('Inactive-owner payload accepted')
    rows=[]
    for bits in (8,12):
        for mode in (0,1):
            settings=dict(sample_hz=40e6,tx_cutoff_hz=20e6,rx_cutoff_hz=9e6,rx_filter_order=5,converter_bits=bits)
            samples=.2*np.exp(2j*math.pi*np.arange(512)/19)
            kwargs=dict(host_mode=mode,transport_allocation='exclusive',converter_clock_config=dict(jitter_amplitude_s=.5e-9),
                rail_config=dict(full_host_activity=True,input_transition_charge_c=.3e-12,inductance_h=5e-9),lo_config=dict(noise_rms_hz=0.))
            observed,report=live_host_rf_observation(samples,settings,**kwargs)
            cut=report['frames']//2
            split,divided=live_host_rf_observation(samples,settings,chunks=(cut,report['frames']-cut),**kwargs)
            assert np.array_equal(observed,split) and report==divided
            assert report['flow']['required_bps']<report['flow']['h2d_capacity_bps']
            rows.append(dict(converter_bits=bits,host_mode=mode,transport=report,chunk_identical=True))
    chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
    flow=chip.transfer(frames=100,mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch)
    assert flow['fault'] is None
    try:chip.configure_transport('legacy')
    except ValueError:pass
    else:raise AssertionError('Active allocation changed')
    return dict(codec_cases=codec_cases,inactive_payload_rejected=True,rf_cases=rows,wire_2p5_transport=flow,
        complete_host_activity=host_activity_controls('exclusive'),active_reconfiguration_rejected=True,
        scope='Exclusive 59-slot codec and live host/RF candidate. Host rate independent of precision; legacy defaults retained for existing controls pending full quality/RTL migration. No new GPIO speed or physical datapath qualification.')


def timed_rf_lifecycle_controls():
    """Retain paired-clock/filter state through muted stop and same-setting rearm."""
    rows=[]
    for fs,bits,coupled in ((5e6,12,False),(10e6,12,True),(20e6,8,True)):
        settings=dict(sample_hz=fs,tx_cutoff_hz=2e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=bits)
        mode=1 if bits==8 else 0;width=2*bits
        def make(reference_edges=8001):
            chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings)
            if coupled:
                chip.attach_reference([i/40e6 for i in range(reference_edges)])
                chip.attach_lo_clock(noise_rms_hz=0.)
                chip.attach_shared_rail(full_host_activity=True,input_transition_charge_c=.3e-12,inductance_h=5e-9)
            chip.attach_rf_stream(lambda i:complex(((chip.stream['tx_buffer']&255)-128)/1024,.05))
            chip.attach_rf_timing(dict(jitter_amplitude_s=.5e-9))
            chip.start();chip.advance(chip.ready_at)
            return chip
        def args(chip):
            return dict(mode=mode,source_hz=fs,sample_bits=width,epoch=chip.epoch,
                tx_prefill_value=0,tx_source=lambda i:(i*53)&1023,**chip.timed_rf_callbacks())
        whole=make();split=make()
        try:whole.transfer(mode=mode,source_hz=fs,sample_bits=width,epoch=whole.epoch,frames=1)
        except ValueError:pass
        else:raise AssertionError('Timed clock bypassed with uniform transport')
        assert whole.stream is None
        old_callbacks=None
        for chip in (whole,split):
            configuration=args(chip)
            flow=chip.transfer(frames=19,**configuration);assert flow['fault'] is None
            if chip is whole:old_callbacks=configuration;stale_index=flow['produced_bits']//width
            chip.stop()
        core=whole.parked_rf;clock=whole.rf_clock;count=core.index;origin=whole.rf_clock_origin
        # Stale transport callbacks may not commit the pending converter edge.
        before=(clock.index,clock.last_time,core.index)
        for callback in ('rx_event_time','rx_source'):
            try:old_callbacks[callback](stale_index)
            except ValueError:pass
            else:raise AssertionError('Stopped converter callback accepted')
        assert before==(clock.index,clock.last_time,core.index)
        expected=copy.deepcopy(core);expected_clock=copy.deepcopy(clock)
        end=whole.time+3.173e-6
        expected_idle=0
        if not coupled:
            while True:
                reference=expected_clock.origin+expected_clock.index*expected_clock.period
                proposal=expected_clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.,
                    jitter_s=.5e-9*math.sin(2*math.pi*1e6*reference))
                if proposal.time>=end:break
                expected_clock.commit(proposal,proposal.time)
                expected.process([0j],sample_times_s=[proposal.time-origin]);expected_idle+=1
        whole.advance(end)
        split.advance(split.time+1.019e-6);split.advance(end)
        assert whole.parked_rf is core and whole.rf_clock is clock and whole.rf_clock_origin==origin
        assert whole.parked_rf.index==split.parked_rf.index>count
        assert whole.rf_clock.index==split.rf_clock.index and whole.rf_clock.last_time==split.rf_clock.last_time
        assert np.allclose(core.rx.state,split.parked_rf.rx.state,rtol=0,atol=1e-12)
        if not coupled:
            assert core.index==expected.index and expected_idle==core.index-count
            assert np.array_equal(core.rx.state,expected.rx.state) and core.previous_tx==expected.previous_tx
            assert core.rng.bit_generator.state==expected.rng.bit_generator.state
        idle_count=core.index-count
        for chip in (whole,split):
            chip.resume_rf_stream(lambda i,owner=chip:complex(((owner.stream['tx_buffer']&255)-128)/1024,.05))
            chip.start();chip.advance(chip.ready_at)
            assert chip.state=='active'
        resumed_base=core.index
        a=args(whole);b=args(split)
        out=whole.transfer(frames=21,**a)
        split.transfer(frames=7,**b);divided=split.transfer(frames=14,**b)
        assert out==divided and out['fault'] is None
        assert whole.stream['rx_words']==split.stream['rx_words']
        assert whole.rf_stream is core and core.index>resumed_base
        assert out['produced_bits']==(core.index-resumed_base)*width
        rows.append(dict(sample_hz=fs,converter_bits=bits,shared_rail_and_lo=coupled,
            muted_idle_samples=idle_count,rearmed_samples=core.index-resumed_base,
            retained_clock_origin_s=origin,split_identical=True))
    # Finite supplied reference stops at 30 us; timed idle must fault and cannot
    # be restarted through the legacy stop/reset convenience path.
    interrupted=make(reference_edges=1201)
    flow=interrupted.transfer(frames=19,**args(interrupted));assert flow['fault'] is None
    interrupted.stop()
    try:interrupted.advance(35e-6)
    except ReferenceLossError:pass
    else:raise AssertionError('Timed idle concealed reference timeout')
    assert interrupted.state=='fault' and abs(interrupted.time-30.1e-6)<1e-18
    interrupted.stop();at=interrupted.time;count=interrupted.parked_rf.index
    for attempt in (lambda:interrupted.advance(36e-6),lambda:interrupted.resume_rf_stream(lambda i:0j),interrupted.start):
        try:attempt()
        except ValueError:pass
        else:raise AssertionError('Unimplemented timed fault recovery accepted')
    assert interrupted.time==at and interrupted.parked_rf.index==count
    return dict(cases=rows,timed_reference_fault_at_s=at,unsupported_fault_recovery_rejected=True,
        uniform_clock_bypass_rejected=True,stale_callbacks_rejected=True,independent_muted_replay=True,
        scope='Same-setting timed stop, muted idle, startup guard and live rearm retain clock/filter/RNG state. Explicit stop discards queued data; no graceful drain, retune or timed fault/reference-loss recovery qualification.')


def converter_timing_controls():
    """Timed filters and live queues; prescribed paired-clock jitter only."""
    from scipy.signal import TransferFunction
    from scipy.linalg import expm
    intervals=np.array([13,29,7,51,23])*1e-9
    # Independent continuous state-space solution for constant held input.
    for order in (1,5):
        model=MultipoleEnvelope(10e6,1e6,order)
        numerator,denominator=butter(order,1.,analog=True)
        state=TransferFunction(numerator,denominator).to_ss()
        value=.2+.1j;elapsed=0.
        for dt in intervals:
            elapsed+=dt*2*math.pi*1e6
            expected=(state.C@np.linalg.solve(state.A,(expm(state.A*elapsed)-np.eye(order))@state.B)).item()*value
            assert abs(model.step(value,dt)-expected)<1e-10
    one=EnvelopeFilter(10e6,1e6)
    for dt in intervals:result=one.step(.2,dt)
    assert abs(result-.2*(1-math.exp(-2*math.pi*1e6*sum(intervals))))<1e-14
    rows=[]
    for fs,bits in ((5e6,12),(10e6,12),(20e6,8),(40e6,8)):
        settings=dict(sample_hz=fs,tx_cutoff_hz=2e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=bits)
        samples=.2*np.exp(2j*math.pi*np.arange(256)/19)
        core=SampledRFStream(settings);uniform=core.process(samples)
        timed=SampledRFStream(settings);stamps=np.arange(len(samples))/fs
        assert np.array_equal(uniform,timed.process(samples,sample_times_s=stamps))
        before=copy.deepcopy(timed.__dict__)
        for bad in ([stamps[-1]],[-1.],[math.nan]):
            try:timed.process([0j],sample_times_s=bad)
            except ValueError:pass
            else:raise AssertionError('Invalid converter timestamp accepted')
        assert timed.index==before['index'] and timed.last_sample_time==before['last_sample_time']
        assert np.array_equal(timed.rx.state,before['rx'].state)
        config=dict(jitter_amplitude_s=.5e-9)
        args=dict(converter_clock_config=config,rail_config=dict(full_host_activity=True),lo_config=dict(noise_rms_hz=0.))
        if fs==40e6:
            try:live_host_rf_observation(samples,settings,**args)
            except LiveRFTransportFailure as failure:
                report=failure.report
                assert report['flow']['fault']=='underflow'
                assert report['flow']['required_bps']>report['flow']['h2d_capacity_bps']
                rows.append(dict(sample_hz=fs,converter_bits=bits,clock=report['converter_clock'],
                    controlled_failure='underflow',required_bps=report['flow']['required_bps'],
                    capacity_bps=report['flow']['h2d_capacity_bps']))
            else:raise AssertionError('Over-capacity conversion demand passed')
            continue
        observed,report=live_host_rf_observation(samples,settings,**args)
        cut=report['frames']//2
        split,split_report=live_host_rf_observation(samples,settings,chunks=(cut,report['frames']-cut),**args)
        assert np.array_equal(observed,split) and report==split_report
        no_jitter,_=live_host_rf_observation(samples,settings,converter_clock_config={},
            rail_config=args['rail_config'],lo_config=args['lo_config'])
        rows.append(dict(sample_hz=fs,converter_bits=bits,clock=report['converter_clock'],
            changed_samples=int(np.count_nonzero(observed!=no_jitter)),chunk_identical=True,
            lo_locked=report['lo_clock']['locked']))
    assert any(row.get('changed_samples',0) for row in rows)
    return dict(cases=rows,independent_filter_solution=True,uniform_grid_equivalence=True,
        invalid_timestamps_rejected=True,scope='Live queues, RF, shared rail and LO with prescribed paired converter jitter; constant buffer supply, no independent remote clock or timed idle/rearm qualification.')


def acquire_chirp_prefix(observed,known,fs,maximum_start=128):
    """Frequency-template acquisition and scalar fit from known prefix only."""
    reference=np.angle(known[1:]*known[:-1].conj())[64:-64]
    centered=reference-reference.mean()
    measured=np.angle(observed[1:]*observed[:-1].conj());best=None
    for lag in range(maximum_start+1):
        row=measured[lag+64:lag+len(known)-65]
        if len(row)!=len(centered):break
        mean=row.mean();row=row-mean
        score=float(row@centered/max(1e-30,np.linalg.norm(row)*np.linalg.norm(centered)))
        if best is None or score>best[0]:best=(score,lag,mean)
    if best is None or best[0]<.8:raise ValueError('Chirp prefix not acquired')
    score,lag,mean=best;frequency=(mean-reference.mean())*fs/(2*math.pi)
    corrected=observed*np.exp(-2j*math.pi*frequency*np.arange(len(observed))/fs)
    gain=np.vdot(known[64:-64],corrected[lag+64:lag+len(known)-64])/np.vdot(known[64:-64],known[64:-64])
    if abs(gain)<.05:raise ValueError('Chirp training gain too small')
    return corrected/gain,dict(start=lag,frequency_hz=float(frequency),correlation=score)


def acquire_live_prefix(observed,known,fs):
    """One external receiver policy: raw acquisition, then fixed 8-tap filter."""
    maximum_start=max(0,len(observed)-len(known))
    try:
        corrected,estimate=acquire_chirp_prefix(observed,known,fs,maximum_start=maximum_start)
        return corrected,dict(estimate,filter_samples=1,raw_failure=None)
    except ValueError as error:
        raw_failure=str(error)
    taps=np.ones(8)/8
    _,estimate=acquire_chirp_prefix(lfilter(taps,[1.],observed),lfilter(taps,[1.],known),fs,maximum_start=maximum_start)
    lag=estimate['start'];frequency=estimate['frequency_hz']
    corrected=observed*np.exp(-2j*math.pi*frequency*np.arange(len(observed))/fs)
    gain=np.vdot(known[64:-64],corrected[lag+64:lag+len(known)-64])/np.vdot(known[64:-64],known[64:-64])
    if abs(gain)<.05:raise ValueError('Filtered acquisition has unusable unfiltered gain')
    return corrected/gain,dict(estimate,filter_samples=8,raw_failure=raw_failure)


def refine_chirp_prefix(observed,known,fs,acquisition):
    """External receiver: fractional timing and residual CFO fit on prefix only."""
    indices=np.arange(64,len(known)-64);reference=known[indices]
    grid=np.arange(len(observed));coarse=acquisition['frequency_hz']
    base=observed*np.exp(-2j*math.pi*coarse*grid/fs);best=None
    for delay in np.linspace(-.5,.5,41):
        start=acquisition['start']+delay;at=start+indices
        row=np.interp(at,grid,base.real)+1j*np.interp(at,grid,base.imag)
        phase=np.unwrap(np.angle(row*reference.conj()))
        slope,intercept=np.polyfit(indices,phase,1)
        aligned=row*np.exp(-1j*slope*indices)
        gain=np.vdot(reference,aligned)/np.vdot(reference,reference)
        if abs(gain)<.05:continue
        error=float(np.mean(abs(aligned/gain-reference)**2)/np.mean(abs(reference)**2))
        if best is None or error<best[0]:best=(error,start,slope,gain)
    if best is None:raise ValueError('Chirp refinement failed')
    error,start,slope,gain=best
    corrected=base*np.exp(-1j*slope*(grid-start))/gain
    return corrected,dict(start=float(start),frequency_hz=float(coarse+slope*fs/(2*math.pi)),
        training_evm_rms=math.sqrt(error),timing_search_samples=.5)


def receiver_affine_fit(observed,reference,indices,fs,acquisition):
 """Bounded external template fit; caller supplies receiver-derived template only."""
 grid=np.arange(len(observed))
 base=observed*np.exp(-2j*np.pi*acquisition['frequency_hz']*grid/fs);best=None
 for ppm in np.arange(-500,501,25):
  scale=1/(1+ppm*1e-6)
  for delta in np.linspace(-1,1,41):
   start=acquisition['start']+delta;at=start+scale*indices
   if at[0]<0 or at[-1]>grid[-1]:continue
   row=np.interp(at,grid,base.real)+1j*np.interp(at,grid,base.imag)
   slope,_=np.polyfit(indices,np.unwrap(np.angle(row*reference.conj())),1)
   aligned=row*np.exp(-1j*slope*indices)
   gain=np.vdot(reference,aligned)/np.vdot(reference,reference)
   error=float(np.mean(abs(aligned/gain-reference)**2)/np.mean(abs(reference)**2))
   if best is None or error<best[0]:best=(error,start,scale,slope,gain,ppm)
 if best is None:raise ValueError('No supported affine receiver fit')
 error,start,scale,slope,gain,ppm=best
 if abs(ppm)==500 or abs(gain)<.05 or not math.isfinite(error) or error>.1**2:
  raise ValueError("Decision-directed fit outside declared envelope")
 return base,best


def gfsk_decision_quality(recovered,*,fs=10e6,limit=.1,symbol_rate_hz=1e6,modulation_index=.5):
    """External decision-derived residual; waveform quality is not integrity."""
    if not all(math.isfinite(v) and v>0 for v in (fs,symbol_rate_hz,modulation_index)):
        raise ValueError('Positive finite modulation settings')
    z=np.asarray(recovered,complex);sps=round(fs/symbol_rate_hz)
    if (z.ndim!=1 or not np.all(np.isfinite(z)) or sps<4 or len(z)<=4*sps
            or (len(z)-4*sps)%sps or not math.isfinite(limit) or limit<=0):
        raise ValueError('Complete finite GFSK waveform required')
    count=(len(z)-4*sps)//sps;dummy=gfsk(np.zeros(count,int),fs=fs,rate=symbol_rate_hz,h=modulation_index)
    decoded=decisions(dummy,z);reference=.2*gfsk(decoded,fs=fs,rate=symbol_rate_hz,h=modulation_index).samples
    window=64*sps
    residual=[float(np.linalg.norm(z[i:i+window]-reference[i:i+window])/np.linalg.norm(reference[i:i+window]))
              for i in range(0,len(z),window)]
    passed=all(value<=limit for value in residual)
    return dict(packet_quality_pass=passed,limit=limit,window_samples=window,
        window_residual_rms=residual,candidate_payload_bits=decoded.tolist() if passed else [],
        integrity_checked=False,
        scope='No residual refit; a different valid codeword still needs external integrity checks')


def decision_directed_gfsk_timing(observed,known,fs=10e6,bits=1024,fit_bits=512,*,symbol_rate_hz=1e6,modulation_index=.5):
 """External observer: first-half provisional decisions, guarded held-out tail."""
 observed=np.asarray(observed,complex);known=np.asarray(known,complex)
 if (observed.ndim!=1 or known.ndim!=1 or len(known)<129 or
     not np.all(np.isfinite(observed)) or not np.all(np.isfinite(known)) or
     not math.isfinite(fs) or fs<=0 or type(bits) is not int or
     type(fit_bits) is not int or not 16<fit_bits<bits):
  raise ValueError('Finite samples and disjoint fit/held-out bit counts required')
 if not all(math.isfinite(v) and v>0 for v in (symbol_rate_hz,modulation_index)):
  raise ValueError('Positive finite modulation settings')
 dummy=gfsk(np.zeros(bits,int),fs=fs,rate=symbol_rate_hz,h=modulation_index)
 if fit_bits*dummy.metadata['sps']<=132:raise ValueError('Insufficient training interior')
 _,coarse=acquire_live_prefix(observed,known,fs)
 initial,acq=refine_chirp_prefix(observed,known,fs,coarse)
 grid=np.arange(len(observed));offset=len(known)+128
 nominal=offset+np.arange(len(dummy.samples));at=acq['start']+nominal
 if at[-1]>grid[-1]:raise ValueError('short capture')
 provisional=np.interp(at,grid,initial.real)+1j*np.interp(at,grid,initial.imag)
 decoded=decisions(dummy,provisional);template=gfsk(decoded,fs=fs,rate=symbol_rate_hz,h=modulation_index)
 local=np.arange(64,fit_bits*dummy.metadata['sps']-64,2);indices=offset+local
 reference=.2*template.samples[local]
 base,(error,start,scale,slope,gain,ppm)=receiver_affine_fit(observed,reference,indices,fs,acq)
 at=start+scale*nominal
 if at[-1]>grid[-1] or at[0]<0:raise ValueError('corrected capture incomplete')
 recovered=(np.interp(at,grid,base.real)+1j*np.interp(at,grid,base.imag))*np.exp(-1j*slope*nominal)/gain
 return recovered,dict(estimated_ppm=int(ppm),fit_evm=float(np.sqrt(error)),start=float(start))

def decision_directed_lora_timing(observed,known,*,fs=5e6,symbols=20,fit_symbols=12):
 """External FPGA diagnostic observer; no transmitted payload or remote rate input.

 Fit four known prefix symbols plus provisional decisions through fit_symbols;
 later symbols are excluded from fitting. Constant affine timing, not a streaming
 tracking loop or a standard packet receiver. Returned waveform is not readiness.
 """
 observed=np.asarray(observed,complex);known=np.asarray(known,complex)
 if (observed.ndim!=1 or known.ndim!=1 or len(known)<129 or
     not np.all(np.isfinite(observed)) or not np.all(np.isfinite(known)) or
     not math.isfinite(fs) or fs<=0 or type(symbols) is not int or
     type(fit_symbols) is not int or not 4<fit_symbols<symbols):
  raise ValueError('Finite waveform and separate fit/holdout symbols required')
 _,coarse=acquire_live_prefix(observed,known,fs)
 initial,acq=refine_chirp_prefix(observed,known,fs,coarse)
 dummy=lora(np.zeros(symbols,int),oversample=16)
 grid=np.arange(len(observed));nominal=np.arange(len(dummy.samples))*fs/dummy.sample_hz
 at=acq['start']+nominal
 if at[0]<0 or at[-1]>grid[-1]:raise ValueError('Incomplete receiver capture')
 provisional=np.interp(at,grid,initial.real)+1j*np.interp(at,grid,initial.imag)
 decoded=decisions(dummy,provisional)
 template=lora(decoded,oversample=16)
 indices=np.arange(64,int(fit_symbols*128*fs/812500)-64,4)
 refs=indices*dummy.sample_hz/fs
 reference=.2*(np.interp(refs,np.arange(len(template.samples)),template.samples.real)+1j*np.interp(refs,np.arange(len(template.samples)),template.samples.imag))
 base,(error,start,scale,slope,gain,ppm)=receiver_affine_fit(observed,reference,indices,fs,acq)
 at=start+scale*nominal
 if at[0]<0 or at[-1]>grid[-1]:raise ValueError('Corrected packet exceeds received capture')
 recovered=(np.interp(at,grid,base.real)+1j*np.interp(at,grid,base.imag))*np.exp(-1j*slope*nominal)/gain
 return recovered,dict(estimated_ppm=int(ppm),fit_evm=float(np.sqrt(error)),start=float(start))


def lora_decision_quality(recovered,*,prefix_symbols=4,limit=.1):
    """Receiver-visible residual against own decisions; no new timing/gain fit.

 This can flag waveform corruption, not replacement by another valid codeword.
 It is an external post-capture packet flag, not silicon readiness or a CRC.
 """
    z=np.asarray(recovered,complex);per_symbol=128*16
    if (z.ndim!=1 or not len(z) or len(z)%per_symbol or not np.all(np.isfinite(z))
            or type(prefix_symbols) is not int or not 0<=prefix_symbols<len(z)//per_symbol
            or not math.isfinite(limit) or limit<=0):
        raise ValueError('Complete finite chirp symbols and positive quality limit required')
    dummy=lora(np.zeros(len(z)//per_symbol,int),oversample=16)
    decoded=decisions(dummy,z);reference=.2*lora(decoded,oversample=16).samples
    residual=np.sqrt(np.mean(abs(z-reference).reshape(-1,per_symbol)**2,axis=1)/.04)
    valid=residual[prefix_symbols:]<=limit
    return dict(packet_quality_pass=bool(np.all(valid)),limit=limit,
        symbol_residual_rms=residual[prefix_symbols:].tolist(),
        failed_payload_symbols=np.flatnonzero(~valid).tolist(),
        decoded_payload_symbols=decoded[prefix_symbols:].tolist(),
        candidate_payload_symbols=decoded[prefix_symbols:].tolist() if np.all(valid) else [],
        integrity_checked=False,
        scope='Decision-derived waveform residual; valid-codeword substitutions require external integrity checks')


def external_lora_payload(*,lo_configuration=None):
    fs=5e6;training=[0,32,64,96]
    payload=np.random.default_rng(953).integers(0,128,16).tolist()
    prefix=lora(training,oversample=16);wave=lora(training+payload,oversample=16)
    nominal=np.arange(math.ceil(prefix.duration*fs))*prefix.sample_hz/fs
    known=.2*(np.interp(nominal,np.arange(len(prefix.samples)),prefix.samples.real)
              +1j*np.interp(nominal,np.arange(len(prefix.samples)),prefix.samples.imag))
    settings=dict(sample_hz=fs,tx_cutoff_hz=2e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    rows=[];failure_controls=[];timeline=np.arange(len(wave.samples))
    for ppm,step_ppm in ((0.,0.),(-100.,0.),(100.,0.),(0.,1000.)):
        def source(t):
            elapsed=t-73/fs-37e-9
            at=(elapsed*(1+ppm*1e-6)+np.maximum(elapsed-12*128/812500,0)*step_ppm*1e-6)*wave.sample_hz
            return .2*(np.interp(at,timeline,wave.samples.real,left=0,right=0)
                        +1j*np.interp(at,timeline,wave.samples.imag,left=0,right=0))
        observed,transport=live_host_rf_observation(np.zeros(math.ceil(wave.duration*fs)+512),settings,
            receive_source=source,offset_hz=48000.,host_mode=0,transport_allocation='exclusive',
            host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
            converter_clock_config=dict(jitter_amplitude_s=.5e-9),
            lo_config=(dict(noise_rms_hz=100000.,noise_seed=830) if lo_configuration is None else lo_configuration),
            rail_config=dict(host_coupling=.1,inductance_h=5e-9,full_host_activity=True,
                input_transition_charge_c=.3e-12,block_write_cap_f=caps['wr_clk'],
                block_read_cap_f=caps['rd_clk'],block_clock_coupling=1.),**declared_rf_noise(.2,12))
        _,coarse=acquire_live_prefix(observed,known,fs)
        corrected,initial=refine_chirp_prefix(observed,known,fs,coarse)
        at=initial['start']+np.arange(len(wave.samples))*fs/wave.sample_hz
        untracked=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
        # The receiver has only samples, known prefix, and declared frame size.
        tracked,estimate=decision_directed_lora_timing(observed,known,fs=fs,symbols=20,fit_symbols=12)
        holdout=12*128*16
        def evm(z,start):return float(np.linalg.norm(z[start:]-.2*wave.samples[start:])/np.linalg.norm(.2*wave.samples[start:]))
        untracked_evm=evm(untracked,len(prefix.samples));heldout_evm=evm(tracked,holdout)
        errors=int(np.count_nonzero(decisions(wave,tracked)[12:]!=payload[8:]))
        quality=lora_decision_quality(tracked)
        assert quality['packet_quality_pass']==(step_ppm==0.)
        assert quality['candidate_payload_symbols']==(payload if step_ppm==0. else [])
        assert (untracked_evm<=.1)==(ppm==0. and step_ppm==0.)
        if step_ppm==0.:assert errors==0 and heldout_evm<=.1
        else:assert heldout_evm>.1
        # Mutation starts beyond the entire fit/search support. It must not
        # change fitted timing or corrected samples in the fitted region.
        cut=math.ceil(initial['start']+12*128*fs/812500*1.001)+64
        changed=observed.copy();changed[cut:]=0
        altered,other=decision_directed_lora_timing(changed,known,fs=fs,symbols=20,fit_symbols=12)
        assert other==estimate and np.array_equal(altered[:holdout],tracked[:holdout])
        rows.append(dict(remote_clock_ppm=ppm,clock_step_ppm=step_ppm,transport=transport,prefix_only=initial,
            untracked_payload_evm_rms=untracked_evm,untracked_heldout_evm_rms=evm(untracked,holdout),
            untracked_quality_pass=untracked_evm<=.1,decision_fit=estimate,
            heldout_evm_rms=heldout_evm,heldout_symbol_errors=errors,heldout_symbols=8,receiver_quality=quality,
            quality_budget=.1,conditional_quality_pass=errors==0 and heldout_evm<=.1 and quality['packet_quality_pass'],holdout_does_not_affect_fit=True))
        if ppm==0. and step_ppm==0.:
            for label,damaged in (
                    ('truncated',observed[:12000]),
                    ('fit_erasure',np.r_[observed[:4000],np.zeros(2500),observed[6500:]]),
                    ('tail_erasure',np.r_[observed[:11000],np.zeros(len(observed)-11000)]),
                    ('tail_phase_step',observed*np.exp(1j*.4*(np.arange(len(observed))>11000)))):
                try:
                    output,fit=decision_directed_lora_timing(damaged,known)
                    check=lora_decision_quality(output)
                except ValueError as error:
                    assert label in ('truncated','fit_erasure')
                    failure_controls.append(dict(case=label,rejected=True,reason=str(error)))
                else:
                    assert label in ('tail_erasure','tail_phase_step') and not check['packet_quality_pass']
                    assert not check['candidate_payload_symbols']
                    failure_controls.append(dict(case=label,rejected=False,receiver_quality=check,fit=fit))
    try:decision_directed_lora_timing(np.zeros_like(observed),known)
    except ValueError:pass
    else:raise AssertionError('Silent input admitted by decision-directed observer')
    substituted=.2*lora(training+[value^1 for value in payload],oversample=16).samples
    assert lora_decision_quality(substituted)['packet_quality_pass']
    return dict(cases=rows,failure_controls=failure_controls,silence_rejected=True,lo_configuration=lo_configuration,
        valid_codeword_substitution_requires_external_integrity_check=True,
        scope='Independent remote LoRa waveform; receiver-derived decisions fit a constant affine rate using prefix plus eight provisional data symbols, final eight symbols excluded. No transmitted labels in observer. Finite seed/clock/load cases; receiver-visible residual flags the tested later rate step/erasures/phase step; not a streaming loop, standard packet, absolute sensitivity, or arbitrary-failure guarantee.')


def connected_lora_payload(transport_allocation='exclusive',*,pulse_clock_config=None,case_labels=None,external_clock_ppm=None,external_launch_s=20e-6+37e-9,receiver_tracking=False,capture_cache=None):
    if type(receiver_tracking) is not bool:raise ValueError('Boolean receiver tracking selection required')
    if external_clock_ppm is not None and (not math.isfinite(external_clock_ppm) or external_clock_ppm<=-1e6):
        raise ValueError('Finite positive external source rate required')
    if not math.isfinite(external_launch_s) or external_launch_s<0:raise ValueError('Finite source launch required')
    fs=5e6;training=[0,32,64,96];payload=[7,53,91,22]
    prefix=lora(training,oversample=16);wave=lora(training+payload,oversample=16)
    def sampled(w):
        indices=np.minimum((np.arange(math.ceil(w.duration*fs))*w.sample_hz/fs).astype(int),len(w.samples)-1)
        return .2*w.samples[indices]
    known=sampled(prefix);samples=np.r_[np.zeros(73),sampled(wave),np.zeros(128)]
    settings=dict(sample_hz=fs,tx_cutoff_hz=2e6,rx_cutoff_hz=1e6,rx_filter_order=5,converter_bits=12)
    results=[];diagnostics=[]
    cases=[('baseline',offset,settings,{}) for offset in (-48000.,0.,48000.)]
    cases += [('no_added_noise',0.,settings,dict(noise_rms=0.)),
              ('wider_existing_filters',0.,dict(settings,tx_cutoff_hz=2.5e6,rx_cutoff_hz=2.5e6),{}),
              ('wider_filters_no_added_noise',0.,dict(settings,tx_cutoff_hz=2.5e6,rx_cutoff_hz=2.5e6),dict(noise_rms=0.))]
    cases += [('common_clock_'+str(scale),48000.,settings,dict(source_clock_scale=scale)) for scale in (.9999,1.0001)]
    cases += [('payload_seed_'+str(seed),offset,settings,{}) for seed,offset in ((941,-48000.),(942,48000.))]
    cases += [('declared_noise',offset,settings,declared_rf_noise(.2,12)) for offset in (-48000.,0.,48000.)]
    cases += [('timed_complete_load',offset,settings,dict(declared_rf_noise(.2,12),
        converter_clock_config=dict(jitter_amplitude_s=.5e-9),
        lo_config=dict(noise_rms_hz=100000.,noise_seed=830),
        rail_config=dict(host_coupling=.1,inductance_h=5e-9,full_host_activity=True,input_transition_charge_c=.3e-12)))
        for offset in (-48000.,0.,48000.)]

    if pulse_clock_config is not None:
        cases.append(('pulse_complete_load',0.,settings,dict(declared_rf_noise(.2,12),
            converter_clock_config=dict(absolute_time=True,jitter_amplitude_s=.5e-9),
            pulse_clock_config=pulse_clock_config,external_substeps=16,
            host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
            rail_config=dict(host_coupling=.1,inductance_h=5e-9,full_host_activity=True,
                input_transition_charge_c=.3e-12,block_write_cap_f=caps['wr_clk'],block_read_cap_f=caps['rd_clk']))))
    if case_labels is not None:
        requested=set(case_labels)
        if not requested or requested-{row[0] for row in cases}:raise ValueError('Unknown or empty LoRa case selection')
        cases=[row for row in cases if row[0] in requested]

    if external_clock_ppm is not None and any(not row[3].get('converter_clock_config',{}).get('absolute_time',False) for row in cases):
        raise ValueError('Independent LoRa source requires absolute converter timing in every selected case')

    for label,offset,configuration,impairments in cases:
        payload=(np.random.default_rng(int(label.rsplit('_',1)[1])).integers(0,128,16).tolist()
                 if label.startswith('payload_seed_') else [7,53,91,22])
        wave=lora(training+payload,oversample=16)
        samples=np.r_[np.zeros(73),sampled(wave),np.zeros(128)]
        drive=samples;remote={}
        if external_clock_ppm is not None:
            timeline=np.arange(len(samples))
            def source(times):
                at=(times-external_launch_s)*fs*(1+external_clock_ppm*1e-6)
                return np.interp(at,timeline,samples.real,left=0,right=0)+1j*np.interp(at,timeline,samples.imag,left=0,right=0)
            remote=dict(receive_source=source);drive=np.zeros_like(samples)
        try:observed,transport=live_host_rf_observation(drive,configuration,host_mode=0,transport_allocation=transport_allocation,offset_hz=offset,**impairments,**remote)
        except LiveRFTransportFailure as error:
            if label not in ('timed_complete_load','pulse_complete_load'):raise
            diagnostics.append(dict(comparison=label,offset_hz=offset,impairments=impairments,
                transport=error.report,conditional_quality_pass=False))
            continue
        if capture_cache is not None:
            capture_cache[(label,offset)]=dict(observed=observed.copy(),known=known.copy(),sample_hz=fs)
        try:corrected,acquisition=acquire_live_prefix(observed,known,fs)
        except ValueError as error:
            diagnostics.append(dict(comparison=label,offset_hz=offset,impairments=impairments,
                acquired=False,reason=str(error),conditional_quality_pass=False))
            continue
        at=acquisition['start']+np.arange(len(wave.samples))*fs/wave.sample_hz
        recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
        decoded=decisions(wave,recovered)[len(training):]
        errors=int(np.count_nonzero(decoded!=payload))
        if label not in ('declared_noise','timed_complete_load','pulse_complete_load'):assert errors==0
        start=len(prefix.samples);evm=float(np.sqrt(np.mean(abs(recovered[start:]-.2*wave.samples[start:])**2)/.04))
        refined,estimate=refine_chirp_prefix(observed,known,fs,acquisition)
        at=estimate['start']+np.arange(len(wave.samples))*fs/wave.sample_hz
        if not len(at) or at[0]<0 or at[-1]>len(refined)-1:
            diagnostics.append(dict(comparison=label,offset_hz=offset,impairments=impairments,
                transport=transport,acquired=True,reason='Incomplete payload window',conditional_quality_pass=False))
            continue
        refined_wave=np.interp(at,np.arange(len(refined)),refined.real)+1j*np.interp(at,np.arange(len(refined)),refined.imag)
        receiver_quality=lora_decision_quality(refined_wave)
        erased=refined_wave.copy();erased[-128*16:]=0
        erased_quality=lora_decision_quality(erased)
        assert not erased_quality['packet_quality_pass'] and not erased_quality['candidate_payload_symbols']
        refined_errors=int(np.count_nonzero(decisions(wave,refined_wave)[len(training):]!=payload))
        refined_evm=float(np.sqrt(np.mean(abs(refined_wave[start:]-.2*wave.samples[start:])**2)/.04))
        changed=observed.copy();changed[acquisition['start']+len(known):]=0
        _,prefix_only=refine_chirp_prefix(changed,known,fs,acquisition)
        assert prefix_only==estimate
        refinement=dict(acquisition=estimate,symbol_errors=refined_errors,evm_rms=refined_evm,
            conditional_quality_pass=refined_errors==0 and refined_evm<=.1,payload_independence=True,
            receiver_quality=receiver_quality,tail_erasure_rejected=True)

        if receiver_tracking:
            fit_symbols=4+len(payload)//2
            tracked,fit=decision_directed_lora_timing(observed,known,fs=fs,
                symbols=4+len(payload),fit_symbols=fit_symbols)
            holdout=fit_symbols*128*16
            quality=lora_decision_quality(tracked)
            holdout_evm=float(np.linalg.norm(tracked[holdout:]-.2*wave.samples[holdout:])/np.linalg.norm(.2*wave.samples[holdout:]))
            cut=math.ceil(estimate['start']+fit_symbols*128*fs/812500*1.001)+64
            altered=observed.copy();altered[cut:]=0
            _,other_fit=decision_directed_lora_timing(altered,known,fs=fs,
                symbols=4+len(payload),fit_symbols=fit_symbols)
            assert fit==other_fit
            damaged=tracked.copy();damaged[-128*16:]=0
            assert not lora_decision_quality(damaged)['packet_quality_pass']
            refinement['tracking']=dict(fit=fit,fit_symbols=fit_symbols,
                heldout_symbols=4+len(payload)-fit_symbols,heldout_evm_rms=holdout_evm,
                heldout_symbol_errors=int(np.count_nonzero(decisions(wave,tracked)[fit_symbols:]!=wave.symbols[fit_symbols:])),
                receiver_quality=quality,heldout_mutation_leaves_fit_unchanged=True,
                erased_tail_rejected=True,uses_transmitted_labels_for_fit=False)

        if offset==0 and label in ('baseline','timed_complete_load'):
            total=transport['frames'];cut=total//2 if label=='timed_complete_load' else 17;split=(cut,total-cut)
            chunked,chunk_report=live_host_rf_observation(samples,configuration,host_mode=0,transport_allocation=transport_allocation,offset_hz=offset,chunks=split,**impairments)
            assert np.array_equal(observed,chunked) and transport==chunk_report
        destination=results if label=='baseline' else diagnostics
        destination.append(dict(comparison=label,settings=configuration,impairments=impairments,offset_hz=offset,transport=transport,acquisition=acquisition,
            symbols=len(payload),symbol_errors=errors,evm_rms=evm,quality_budget=.1,prefix_refinement=refinement,
            conditional_quality_pass=errors==0 and evm<=.1))
    timed=[row for row in diagnostics if row['comparison']=='timed_complete_load']
    if case_labels is None or 'timed_complete_load' in case_labels:
        assert len(timed)==3 and all(row.get('prefix_refinement',{}).get('conditional_quality_pass',False) for row in timed)
    try:acquire_chirp_prefix(np.zeros(len(samples),complex),known,fs)
    except ValueError:pass
    else:raise AssertionError('Silent chirp acquired')
    return dict(external_clock_ppm=external_clock_ppm,external_launch_s=external_launch_s,transport_allocation=transport_allocation,cases=results,controlled_comparisons=diagnostics,chunk_invariant_at_zero_offset=any(label in ('baseline','timed_complete_load') and offset==0 for label,offset,_,_ in cases),silence_rejected=True,
        scope='Synthetic known-chirp prefix; delivered host samples only. Four-symbol controls and two seeded sixteen-symbol payloads; waveform EVM failures retained. No standard packet, sensitivity or unbounded-burst qualification.')


def declared_rf_noise(amplitude,bits,a=None,*,frontend_input_referred=True):
    """Projection noise assumptions expressed in live-core complex RMS units.

    Default separates filter-output frontend noise from ADC-input noise.
    Explicit frontend_input_referred=False retains the legacy post-gain reduction.
    Added ENOB noise excludes quantization already supplied by the ADC model.
    IID phase is a budget reduction, not a physical oscillator noise spectrum.
    """
    a=Assumptions() if a is None else a
    step=2**(1-bits)
    adc_variance=max(0.,2**(2*(1-a.converter_enob))-step**2)/12
    if frontend_input_referred:
        return dict(noise_rms=math.sqrt(2*adc_variance),
                    frontend_noise_rms=amplitude*a.frontend_evm_rms,
                    phase_rms_rad=a.relative_lo_phase_rms_rad)
    # Legacy combined output-referred reduction, retained for matched history.
    return dict(noise_rms=math.sqrt((amplitude*a.frontend_evm_rms)**2+2*adc_variance),
                phase_rms_rad=a.relative_lo_phase_rms_rad)


def rf_demonstration_rail(bias_current_a):
    """Shared RF demonstration load: actual mapped FIFO clock pins plus bias.

    Mapping capacitance is evidence; coupling, package and bias remain declared
    assumptions. Internal cell/clock-tree/data power is not inferred from pins.
    """
    if not math.isfinite(bias_current_a) or bias_current_a<0:
        raise ValueError('Finite nonnegative RF bias required')
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    return dict(host_coupling=.1,inductance_h=5e-9,full_host_activity=True,
        input_transition_charge_c=.3e-12,bias_current_a=bias_current_a,
        block_write_cap_f=caps['wr_clk'],block_read_cap_f=caps['rd_clk'])


def tx_ofdm_crest_screen(seeds=range(950,982),*,tx_voltage_scale=5.02,
        source_resistance_ohm=50.,load_resistance_ohm=50.,peak_current_limit_a=.020,capture=None,interpolation="repeat",ideal_output=False,tx_cutoff_hz=10e6):
    """Cheap DAC/filter/driver current screen; no host/clock/quality verdict."""
    from tx_output_candidate import PARAMETERS
    if interpolation not in ('repeat','fir') or type(ideal_output) is not bool:
        raise ValueError('Explicit interpolation and output control required')
    if not all(math.isfinite(v) and v>0 for v in (tx_voltage_scale,source_resistance_ohm,load_resistance_ohm,peak_current_limit_a)):
        raise ValueError('Positive finite driver/load requirements needed')
    seeds=tuple(seeds)
    if not seeds or any(type(seed) is not int or seed<0 for seed in seeds):
        raise ValueError('Nonnegative integer payload seeds required')
    fs=40e6;substeps=16;training=fixture('wifi_he20',seed=1907)
    settings=dict(sample_hz=fs,tx_cutoff_hz=tx_cutoff_hz,rx_cutoff_hz=5e6,
                  rx_filter_order=5,converter_bits=12,rx_gain=1.)
    rows=[]
    for seed in seeds:
        wave=fixture('wifi_he20',seed=seed);times=[];voltage=[]
        def observe(t,z):
            times.extend(t);voltage.extend(z*load_resistance_ohm/(source_resistance_ohm+load_resistance_ohm))
        core=SampledRFStream(settings,external_substeps=substeps,noise_rms=0.,
            tx_output_parameters=({key:0. for key in PARAMETERS} if ideal_output else PARAMETERS),tx_volts_per_unit=tx_voltage_scale,tx_port_observer=observe)
        source=.15*np.r_[training.samples,wave.samples]
        dac_input=(np.repeat(source,2) if interpolation=='repeat' else
                   bandlimited_samples(source,np.arange(2*len(source))/2))
        samples=np.r_[dac_input,0j]
        core.process(samples,sample_times_s=(np.arange(len(samples))+1)/fs)
        start=2*len(training.samples);count=2*len(wave.samples)
        active=slice((start+1)*substeps,(start+count+1)*substeps)
        t=np.asarray(times);z=np.asarray(voltage)
        if capture is not None:
            capture.append(dict(payload_seed=seed,times_s=t[active].copy(),loaded_voltage=z[active].copy()))
        power=rf_tx_power_requirement(t[active],z[active],substeps=substeps,
            source_resistance_ohm=source_resistance_ohm,load_resistance_ohm=load_resistance_ohm,target_average_power_w=.001)
        sampled_peak=float(np.max(abs(z)))/load_resistance_ohm
        peak=core.tx_peak_open_v/(source_resistance_ohm+load_resistance_ohm)
        rows.append(dict(payload_seed=seed,sampled_peak_current_a=sampled_peak,peak_current_a=peak,within_current_limit=peak<=peak_current_limit_a,
            dac_clips=core.dac_clips,**power))
    return dict(interpolation=interpolation,ideal_output=ideal_output,tx_cutoff_hz=tx_cutoff_hz,
        fpga_lookahead_input_samples=32 if interpolation=='fir' else 0,
        tx_voltage_scale=tx_voltage_scale,source_resistance_ohm=source_resistance_ohm,load_resistance_ohm=load_resistance_ohm,peak_current_limit_a=peak_current_limit_a,cases=rows,failed_current_cases=sum(not r['within_current_limit'] for r in rows),
        scope='Uniform DAC timestamps, actual quantization/filter/declared nonlinear driver, declared resistive differential load. Peak current is the analytic interval-end bound for this one-pole/monotonic output model, not a midpoint maximum. No host, synthesizer/supply, standard acquisition, EVM or emission-mask qualification.')


def connected_tx_gfsk_port(**kwargs):
    """Compatibility entry for the independent GFSK TX diagnostic."""
    kwargs.setdefault('complete_rail_load',False) # Retain the historical comparison.
    return connected_tx_port(waveform='gfsk',**kwargs)


def connected_tx_port(*,waveform='gfsk',tx_amplitude=.2,receiver_clock_ppm=100.,payload_seed=954,
        split_time=False,pulse_noise_rms_hz=100000.,capture_cache=None,tx_output_parameters=None,bias_current_a=0.,tx_electrical_budget=None,tx_substeps=4,observer_filter=None,tx_voltage_scale=.5,complete_rail_load=True,wait_for_acquisition=False):
    """Independent ideal observer of loaded TX voltage; prefix-only fitting.

    Keeps actual pulse synthesizer and staged host transport. Optional existing
    memoryless driver parameters are assumptions; load/observer remain ideal.
    """
    if type(complete_rail_load) is not bool:raise ValueError('Boolean rail-load selection required')
    if type(wait_for_acquisition) is not bool:raise ValueError('Boolean acquisition wait required')
    if not math.isfinite(receiver_clock_ppm) or abs(receiver_clock_ppm)>1000:
        raise ValueError('Receiver clock outside diagnostic envelope')
    if not math.isfinite(pulse_noise_rms_hz) or pulse_noise_rms_hz<0:
        raise ValueError('Finite nonnegative oscillator noise required')
    if type(tx_substeps) is not int or not 2<=tx_substeps<=64:
        raise ValueError('Power-qualified TX capture needs 2 through 64 midpoints per interval')
    if waveform not in ('gfsk','he20') or not math.isfinite(tx_amplitude) or not 0<tx_amplitude<=.2:
        raise ValueError('Supported diagnostic waveform and amplitude in (0,.2] required')
    if waveform=='gfsk' and observer_filter is not None:
        raise ValueError('Select the explicit OFDM observer for filtered capture')
    fs=40e6;known=diagnostic_chirp_prefix(fs)
    if waveform=='gfsk':
        bits=np.random.default_rng(payload_seed).integers(0,2,128)
        wave=gfsk(bits,fs=fs);body=tx_amplitude*wave.samples
    else:
        wave=fixture('wifi_he20',seed=payload_seed);training=fixture('wifi_he20',seed=1907)
        train=tx_amplitude*training.samples
        body=np.repeat(np.r_[train,tx_amplitude*wave.samples],2)
    samples=np.r_[np.zeros(73),known,np.zeros(128),body,np.zeros(256)]
    times=[];voltages=[];peak_open=0.
    port_args=dict(source_resistance_ohm=50.,load_resistance_ohm=50.)
    if tx_electrical_budget is not None:
        for key in port_args:port_args[key]=tx_electrical_budget[key]
        rf_tx_compliance_budget(peak_open_v=0.,minimum_supply_v=3.3,
            total_rail_bias_a=bias_current_a,**tx_electrical_budget)
    def observe(t,z):
        nonlocal peak_open
        peak_open=max(peak_open,float(np.max(abs(z))))
        loaded=rf_tx_resistive_port(z,**port_args)
        times.extend(t);voltages.extend(loaded['envelope_v'])
    settings=dict(sample_hz=fs,tx_cutoff_hz=10e6,rx_cutoff_hz=5e6,
                  rx_filter_order=5,converter_bits=12,rx_gain=1.)
    frames=math.ceil((len(samples)+256)/fs*250e6/64)
    chunks=(frames//2,frames-frames//2) if split_time else None
    rail_config=(rf_demonstration_rail(bias_current_a) if complete_rail_load else
        dict(host_coupling=.1,full_host_activity=True,input_transition_charge_c=.3e-12,bias_current_a=bias_current_a))
    _,transport=live_host_rf_observation(samples,settings,host_mode=0,chunks=chunks,
        transport_allocation='exclusive',host_block_words=8,host_cdc_read_hz=40e6,
        host_cdc_phase=.37,rail_config=rail_config,
        pulse_clock_config=dict(rate_hz=2437000000,reference_hz=120e6,
                               bandwidth_hz=1.5e6,fast_fraction=.25,noise_rms_hz=pulse_noise_rms_hz,
                               require_acquisition=wait_for_acquisition,wait_for_acquisition=wait_for_acquisition),
        converter_clock_config=dict(absolute_time=True,jitter_amplitude_s=.5e-9),
        external_substeps=tx_substeps,tx_port_observer=observe,tx_volts_per_unit=tx_voltage_scale,
        tx_output_parameters=tx_output_parameters)
    t=np.asarray(times);z=np.asarray(voltages)
    peak_open=max(peak_open,transport['tx_peak_open_v'])
    if capture_cache is not None:
        capture_cache.update(times=t,voltage=z,transport=transport,known=known,fs=fs)
    if waveform=='gfsk':
        recovered,fit,quality=receive_tx_gfsk_port(t,z,known,fs=fs,symbols=len(bits),
                                                receiver_clock_ppm=receiver_clock_ppm)
        quality=gfsk_decision_quality(recovered*.2/tx_amplitude,fs=fs)
        errors=int(np.count_nonzero(decisions(wave,recovered)!=bits))
        reference=tx_amplitude*wave.samples
    else:
        recovered,fit,quality=receive_tx_he20_port(t,z,known,training,train,fs=fs,
            payload_blocks=4,receiver_clock_ppm=receiver_clock_ppm,observer_filter=observer_filter)
        errors=int(np.count_nonzero((recovered.real>0).ravel()!=wave.symbols))
        oracle=TrainedBlockEqualizer(256,wave.metadata['cp'],np.asarray(wave.metadata['data'])%256)
        reference=oracle.spectrum(tx_amplitude*wave.samples)
    evm=float(np.linalg.norm(recovered-reference)/np.linalg.norm(reference))
    payload_start=73+len(known)+128+(2*len(train) if waveform=='he20' else 0)
    payload_count=len(wave.samples)*(2 if waveform=='he20' else 1)
    active=slice((payload_start+1)*tx_substeps,(payload_start+payload_count+1)*tx_substeps)
    power_requirement=rf_tx_power_requirement(t[active],z[active],substeps=tx_substeps,
        target_average_power_w=Assumptions().rf_output_power_w,**port_args)
    return dict(complete_rail_load=complete_rail_load,active_payload_power=power_requirement,tx_voltage_scale=tx_voltage_scale,transport=transport,waveform=waveform,tx_amplitude=tx_amplitude,tx_substeps=tx_substeps,observer_filter=observer_filter,receiver_clock_ppm=receiver_clock_ppm,
        tx_output_parameters=tx_output_parameters,
        acquisition=fit,quality=quality,payload_errors=errors,payload_evm_rms=evm,
        sampled_peak_delivered_power_w=float(np.max(abs(z)**2)/(2*port_args['load_resistance_ohm'])),
        peak_delivered_power_w=peak_open**2*port_args['load_resistance_ohm']/
            (2*(port_args['source_resistance_ohm']+port_args['load_resistance_ohm'])**2),
        electrical_budget=(None if tx_electrical_budget is None else rf_tx_compliance_budget(
            peak_open_v=peak_open,minimum_supply_v=transport['shared_rail']['minimum_v'],
            total_rail_bias_a=bias_current_a,**tx_electrical_budget)),
        scope='Actual TX LO and loaded resistive envelope, optional declared memoryless IQ/leakage/cubic driver and constant rail bias; ideal independent observer, no driver noise/matching/signal-dependent current or physical parameter/standard acquisition claim')


def sample_rf_voltage(times,voltage,*,sample_hz,clock_ppm,observer_filter=None):
    """Independent voltage sampler with optional explicit pre-sampling filter.

    Finite capture interpolation is an observation approximation, not a source
    of additional bandwidth. Filter starts at zero at the capture boundary.
    """
    t=np.asarray(times,float);z=np.asarray(voltage,complex)
    if (t.ndim!=1 or len(t)<2 or z.shape!=t.shape or not np.all(np.isfinite(t))
            or not np.all(np.isfinite(z)) or not np.all(np.diff(t)>0)
            or not math.isfinite(sample_hz) or sample_hz<=0
            or not math.isfinite(clock_ppm) or abs(clock_ppm)>1000):
        raise ValueError('Finite ordered voltage capture and bounded sample clock required')
    if observer_filter is not None:
        from scipy.signal import sosfilt
        if set(observer_filter)!={'sample_hz','cutoff_hz','order'}:
            raise ValueError('Declare receiver filter sampling, cutoff and order')
        rate=observer_filter['sample_hz'];cutoff=observer_filter['cutoff_hz'];order=observer_filter['order']
        if (not math.isfinite(rate) or not math.isfinite(cutoff) or not 0<cutoff<rate/2
                or type(order) is not int or not 1<=order<=8
                or rate>1.001*(len(t)-1)/(t[-1]-t[0])):
            raise ValueError('Filter must fit available observation resolution')
        uniform=np.arange(t[0],t[-1],1/rate)
        values=np.interp(uniform,t,z.real)+1j*np.interp(uniform,t,z.imag)
        z=sosfilt(butter(order,cutoff,fs=rate,output='sos'),values);t=uniform
    step=1/(sample_hz*(1+clock_ppm*1e-6))
    grid=np.arange(t[0]+.37*step,t[-1],step)
    return np.interp(grid,t,z.real)+1j*np.interp(grid,t,z.imag)


def receive_tx_he20_port(times,voltage,known,training,train,*,fs,payload_blocks,receiver_clock_ppm,observer_filter=None):
    """Independent OFDM observer; training/pilots/decisions only, no payload oracle."""
    received=sample_rf_voltage(times,voltage,sample_hz=fs,clock_ppm=receiver_clock_ppm,
                               observer_filter=observer_filter)
    _,coarse=acquire_live_prefix(received,known,fs)
    corrected,fit=refine_chirp_prefix(received,known,fs,coarse)
    meta=training.metadata;count=len(train)+payload_blocks*(256+meta['cp'])
    coordinates=fit['start']+len(known)+128+2*np.arange(count)
    recovered=windowed_sinc_samples(corrected,coordinates)
    rate=training_clock_rate(train,recovered[:len(train)],256,meta['cp'],meta['data'])
    coordinates=fit['start']+len(known)+128+2*np.arange(count)/(1+rate['rate_error_ppm']*1e-6)
    recovered=windowed_sinc_samples(corrected,coordinates)
    eq=TrainedBlockEqualizer(256,meta['cp'],np.asarray(meta['data'])%256,channel_delays=range(16))
    pilots=TrainedBlockEqualizer(256,meta['cp'],np.asarray(meta['pilots'])%256)
    eq.train(train,recovered[:len(train)]);pilots.train(train,recovered[:len(train)])
    data,pilot_values,_=pilot_timing_correct(eq.observe(recovered[len(train):]),
        pilots.observe(recovered[len(train):]),meta['data'],meta['pilots'])
    amplitude=float(np.median(abs(eq.spectrum(train))))
    data,_=crossfit_constellation_phase(data,meta['data'],[-amplitude,amplitude])
    decision=constellation_quality(data,[-amplitude,amplitude])
    quality=dict(packet_quality_pass=decision['accepts'],decision_quality=decision,
        pilot_quality=known_pilot_quality(pilot_values,pilots.spectrum(train)[0]),
        integrity_checked=False,limit=.1)
    return data,dict(fit,training_clock_rate=rate),quality


def receive_tx_gfsk_port(times,voltage,known,*,fs,symbols,receiver_clock_ppm):
    """External prefix-only receiver; no transmitted payload argument.

    Ideal sampling/linear interpolation of already loaded voltage. The fixed
    128-sample guard is part of this diagnostic packet, not a chip command.
    """
    t=np.asarray(times,float);z=np.asarray(voltage,complex)
    known=np.asarray(known,complex)
    if (t.ndim!=1 or len(t)<2 or z.shape!=t.shape or not np.all(np.isfinite(t))
            or not np.all(np.isfinite(z)) or not np.all(np.diff(t)>0)
            or not math.isfinite(fs) or fs<=0 or type(symbols) is not int or symbols<1
            or not math.isfinite(receiver_clock_ppm) or abs(receiver_clock_ppm)>1000):
        raise ValueError('Finite ordered capture and supported receiver timing required')
    # Receiver grid is independent of individual DAC event timestamps.
    step=1/(fs*(1+receiver_clock_ppm*1e-6))
    grid=np.arange(t[0]+.37*step,t[-1],step)
    received=np.interp(grid,t,z.real)+1j*np.interp(grid,t,z.imag)
    _,coarse=acquire_live_prefix(received,known,fs)
    corrected,fit=refine_chirp_prefix(received,known,fs,coarse)
    count=len(gfsk(np.zeros(symbols,int),fs=fs).samples)
    at=fit['start']+len(known)+128+np.arange(count)
    if at[-1]>=len(corrected):raise ValueError('Incomplete independent capture')
    recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
    return recovered,fit,gfsk_decision_quality(recovered,fs=fs)


def rf_tx_power_requirement(times,loaded_voltage,*,substeps,source_resistance_ohm,
        load_resistance_ohm,target_average_power_w):
    """Time-weight midpoint captures and derive linear power-scaling demands.

    The result is a required swing/current, not a prediction that the same
    nonlinear driver can provide it. Select the active payload window before
    calling; do not average startup/idle into an active-transmit power claim.
    """
    t=np.asarray(times,float);z=np.asarray(loaded_voltage,complex)
    if (type(substeps) is not int or substeps<2 or t.ndim!=1 or not len(t)
            or len(t)%substeps or z.shape!=t.shape or not np.all(np.isfinite(t))
            or not np.all(np.isfinite(z)) or not np.all(np.diff(t)>0)
            or not all(math.isfinite(x) and x>0 for x in
                (source_resistance_ohm,load_resistance_ohm,target_average_power_w))):
        raise ValueError('Finite midpoint capture and positive power/impedance required')
    rows=t.reshape(-1,substeps);steps=np.diff(rows,axis=1)
    spacing=(rows[:,-1]-rows[:,0])/(substeps-1)
    if not np.allclose(steps,spacing[:,None],rtol=1e-8,atol=1e-18):
        raise ValueError('Uniform midpoints within each converter interval required')
    durations=spacing*substeps
    if len(rows)>1 and not np.allclose(rows[1:,0]-spacing[1:]/2,
            rows[:-1,-1]+spacing[:-1]/2,rtol=0,atol=1e-15):
        raise ValueError('Contiguous converter intervals required')
    weights=np.repeat(spacing,substeps);power=abs(z)**2/(2*load_resistance_ohm)
    duration=float(np.sum(durations));average=float(np.sum(power*weights)/duration)
    if average<=0:raise ValueError('Nonzero transmitted power required')
    peak=float(np.max(abs(z)));scale=math.sqrt(target_average_power_w/average)
    required_current=peak/load_resistance_ohm*scale
    return dict(capture_duration_s=duration,average_load_power_w=average,
        peak_envelope_load_power_w=float(np.max(power)),
        peak_to_average_power=float(np.max(power)/average),target_average_power_w=target_average_power_w,
        required_linear_voltage_scale=scale,required_peak_load_current_a=required_current,
        required_peak_open_v=required_current*(source_resistance_ohm+load_resistance_ohm),
        scope='Midpoint-weighted active-payload power; linear scaling gives required swing/current only, not achievable output or preserved EVM')


def rf_tx_compliance_budget(*,peak_open_v,minimum_supply_v,total_rail_bias_a,
        source_resistance_ohm,load_resistance_ohm,driver_bias_current_a,
        peak_current_limit_a,headroom_per_rail_v,differential=False):
    """Declared Thevenin driver bounds, not a transistor implementation proof.

    Each output leg is centered at VDD/2 with an AC-coupled external load
    (no DC termination current). Differential voltage/impedance are across both
    legs; do not reuse per-leg values as differential ones. Use minimum rail and maximum RF
    envelope over the capture; rejection means the bound cannot certify that
    operating point, not a simulated clipped waveform. Bias is already charged
    to the shared rail, so the reserved driver allocation is not added twice.
    """
    if type(differential) is not bool:raise ValueError('Explicit Boolean output topology required')
    if (not math.isfinite(peak_open_v) or peak_open_v<0 or
            not math.isfinite(headroom_per_rail_v) or headroom_per_rail_v<0 or
            not all(math.isfinite(x) and x>0 for x in (minimum_supply_v,total_rail_bias_a,
                source_resistance_ohm,load_resistance_ohm,driver_bias_current_a,peak_current_limit_a))):
        raise ValueError('Finite positive declared electrical budget required')
    if driver_bias_current_a>total_rail_bias_a or peak_current_limit_a>driver_bias_current_a:
        raise ValueError('Driver current reservation must fit the modeled rail bias')
    current=peak_open_v/(source_resistance_ohm+load_resistance_ohm)
    voltage_limit=max(0.,minimum_supply_v/2-headroom_per_rail_v)*(2 if differential else 1)
    rf_power=current**2*(source_resistance_ohm+load_resistance_ohm)/2
    dc_power=minimum_supply_v*driver_bias_current_a
    checks=dict(voltage_headroom=peak_open_v<=voltage_limit,
                peak_current=current<=peak_current_limit_a,energy=rf_power<=dc_power)
    return dict(within_declared_compliance=all(checks.values()),checks=checks,
        topology='differential' if differential else 'single_ended',
        peak_open_v=peak_open_v,allowed_open_peak_v=voltage_limit,peak_load_current_a=current,
        peak_current_limit_a=peak_current_limit_a,driver_bias_current_a=driver_bias_current_a,
        total_rail_bias_a=total_rail_bias_a,minimum_supply_v=minimum_supply_v,
        peak_envelope_rf_power_w=rf_power,minimum_driver_dc_power_w=dc_power,
        peak_load_power_w=current**2*load_resistance_ohm/2,
        scope='Conservative declared port voltage/current/energy bounds; no physical parameter validation, clipping waveform, noise or matching-network qualification')


def rf_tx_resistive_port(envelope_v,*,source_resistance_ohm,load_resistance_ohm):
    """Load a declared Thevenin open-circuit complex RF voltage envelope.

    This is a reference-plane accounting model, not a driver implementation.
    Samples are instantaneous envelopes: callers must time-weight powers when
    integrating nonuniform observations. No PA, matching network or noise implied.
    """
    z=np.asarray(envelope_v,dtype=complex)
    if not np.all(np.isfinite(z)) or not all(math.isfinite(r) and r>0 for r in
            (source_resistance_ohm,load_resistance_ohm)):
        raise ValueError('Finite envelope and positive resistances required')
    current=z/(source_resistance_ohm+load_resistance_ohm)
    loaded=current*load_resistance_ohm
    return dict(envelope_v=loaded,load_power_w=np.abs(current)**2*load_resistance_ohm/2,
        source_dissipation_w=np.abs(current)**2*source_resistance_ohm/2,
        available_power_w=np.abs(z)**2/(8*source_resistance_ohm))


def rf_receiver_electrical_budget(*,temperature_k,noise_bandwidth_hz,noise_figure_db,
        conversion_voltage_gain_db,volts_per_normalized_unit,resistance_ohm=50.,
        signal_normalized_rms=.2):
    """Declared matched-input budget mapped to pre-PGA complex-envelope units.

    vRF=Re{z exp(jwt)}, P=E|z|^2/(2R). Conversion gain maps matched RF
    envelope voltage to pre-PGA I/Q voltage. NF/ENBW/gain are requirements,
    not claims about realizable transistors; noise is integrated at filter output.
    """
    positive=(temperature_k,noise_bandwidth_hz,volts_per_normalized_unit,
              resistance_ohm,signal_normalized_rms)
    if not all(math.isfinite(x) and x>0 for x in positive) or not all(
            math.isfinite(x) for x in (noise_figure_db,conversion_voltage_gain_db)) or noise_figure_db<0:
        raise ValueError('Finite positive RF reference-plane parameters required')
    gain=10**(conversion_voltage_gain_db/20)
    noise_w=1.380649e-23*temperature_k*noise_bandwidth_hz*10**(noise_figure_db/10)
    signal_v=signal_normalized_rms*volts_per_normalized_unit/gain
    signal_w=signal_v**2/(2*resistance_ohm)
    normalized_noise=math.sqrt(2*resistance_ohm*noise_w)*gain/volts_per_normalized_unit
    if not all(math.isfinite(v) and v>0 for v in (gain,noise_w,signal_w,normalized_noise)):
        raise ValueError('Electrical budget outside representable range')
    return dict(input_signal_dbm=10*math.log10(signal_w/1e-3),
        input_noise_dbm=10*math.log10(noise_w/1e-3),
        frontend_noise_rms=normalized_noise,frontend_evm_rms=normalized_noise/signal_normalized_rms,
        scope='Declared matched RF input to pre-PGA filter-output noise mapping; no TX, blocker, compression or physical NF/gain qualification')


def diagnostic_chirp_prefix(fs,bandwidth=1625000.):
    """Shared external acquisition stimulus; not an on-chip protocol feature."""
    training=lora([0,8,16,24],sf=5,bandwidth=bandwidth,oversample=16)
    indices=np.minimum((np.arange(math.ceil(training.duration*fs))*training.sample_hz/fs).astype(int),len(training.samples)-1)
    return .2*training.samples[indices]


def connected_he20_payload(transport_allocation='exclusive',*,combined_lo_config=None,pulse_clock_config=None,pulse_converter_jitter_s=.5e-9,pulse_bias_current_a=0.,external_launch_s=None,case_labels=None,settings_overrides=None,remote_clock_ppm=None,pilot_timing=False,receiver_sinc=False,capture_cache=None,training_rate=False,external_substeps=0,payload_seed=951,frontend_input_referred=True,electrical_budget=None,channel_delays=None,decision_phase=False,remote_fault=None):
    if not math.isfinite(pulse_bias_current_a) or pulse_bias_current_a<0 or (pulse_bias_current_a and pulse_clock_config is None):
        raise ValueError('Declared bias requires a pulse-clock rail case')
    if not math.isfinite(pulse_converter_jitter_s) or not 0<=pulse_converter_jitter_s<=.75e-9:
        raise ValueError('Bounded converter timing modulation required')
    if pulse_clock_config is not None and combined_lo_config is not None:
        raise ValueError('Choose one RF clock owner')
    if external_launch_s is None:external_launch_s=(20e-6 if pulse_clock_config is not None else 0.)+37e-9
    if not math.isfinite(external_launch_s) or external_launch_s<0:raise ValueError('Finite nonnegative source launch required')
    if electrical_budget is not None and not frontend_input_referred:
        raise ValueError('Electrical frontend noise must precede the PGA')
    electrical=rf_receiver_electrical_budget(**electrical_budget) if electrical_budget is not None else None
    def noise_budget(*args):
        result=declared_rf_noise(*args,frontend_input_referred=frontend_input_referred)
        if electrical is not None:result['frontend_noise_rms']=electrical['frontend_noise_rms']
        return result
    fs=40e6;known=diagnostic_chirp_prefix(fs)
    settings=dict(sample_hz=fs,tx_cutoff_hz=20e6,rx_cutoff_hz=9.157407e6,rx_filter_order=5,converter_bits=12)
    if settings_overrides:settings.update(settings_overrides)
    if type(payload_seed) is not int or payload_seed<0:raise ValueError('Nonnegative integer payload seed required')
    wave=fixture('wifi_he20',seed=payload_seed);training=fixture('wifi_he20',seed=1907)
    payload=.2*wave.samples;train=.2*training.samples
    samples=np.r_[np.zeros(73),known,np.zeros(128),np.repeat(np.r_[train,payload],2),np.zeros(128)]
    if remote_fault not in (None,'tail_erasure','late_phase_step','silence','training_erasure'):
        raise ValueError('Unknown external waveform fault')
    if remote_fault is not None and remote_clock_ppm is None:
        raise ValueError('Waveform fault requires an independent source')
    source_options={};local_samples=samples
    if remote_clock_ppm is not None:
        if not math.isfinite(remote_clock_ppm) or abs(remote_clock_ppm)>1000:
            raise ValueError('Finite bounded remote clock error required')
        timeline=np.arange(len(samples))
        def receive_source(time):
            at=(time-external_launch_s)*fs*(1+remote_clock_ppm*1e-6)
            result=np.interp(at,timeline,samples.real,left=0,right=0)+1j*np.interp(at,timeline,samples.imag,left=0,right=0)
            # Physical source damage halfway through payload, not an observer hint.
            boundary=73+len(known)+128+2*len(train)+len(payload)
            if remote_fault=='silence':result=np.zeros_like(result)
            if remote_fault=='training_erasure':
                start=73+len(known)+128
                result=np.where((at>=start)&(at<start+2*len(train)),0j,result)
            if remote_fault=='tail_erasure':result=np.where(at>=boundary,0j,result)
            if remote_fault=='late_phase_step':result=result*np.exp(.8j*(at>=boundary+73))
            return result
        source_options=dict(receive_source=receive_source,external_substeps=external_substeps);local_samples=np.zeros(len(samples))
    results=[]
    cases=[('minimal',offset,{}) for offset in (-48000.,0.,48000.)]
    cases += [('declared_noise',offset,noise_budget(.2,12)) for offset in (-48000.,0.,48000.)]
    cases += [('shared_rail_'+str(coupling),0.,dict(noise_budget(.2,12),rail_config=dict(host_coupling=coupling))) for coupling in (0.,.1,1.)]
    cases += [(label,0.,dict(noise_budget(.2,12),rail_config=dict(host_coupling=1.,**parameters)))
              for label,parameters in [('shared_gain_only',dict(lo_hz_per_v=0.)),
                                       ('shared_half_sensitivity',dict(lo_hz_per_v=5e6)),
                                       ('shared_phase_only',dict(rf_gain_fraction=0.)),
                                       ('shared_effects_disabled',dict(lo_hz_per_v=0.,rf_gain_fraction=0.))]]
    cases += [('shared_inductance_'+str(inductance),0.,dict(noise_budget(.2,12),rail_config=dict(host_coupling=1.,lo_hz_per_v=5e6,inductance_h=inductance))) for inductance in (1e-9,5e-9,10e-9)]
    cases += [('shared_capacitance_'+str(capacitance)+'_'+str(coupling),0.,
               dict(noise_budget(.2,12),rail_config=dict(host_coupling=coupling,lo_hz_per_v=5e6,inductance_h=5e-9,capacitance_f=capacitance)))
              for capacitance in (100e-12,300e-12) for coupling in (.1,1.)]
    cases += [('excess_noise',0.,noise_budget(.2,12,replace(Assumptions(),relative_lo_phase_rms_rad=.3,frontend_evm_rms=.4)))]
    if combined_lo_config is not None:
        caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
        cases += [('combined_clock_'+str(coupling),offset,dict(noise_budget(.2,12),
            lo_config=combined_lo_config,host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
            converter_clock_config=dict(jitter_amplitude_s=.5e-9),
            rail_config=dict(host_coupling=coupling,inductance_h=5e-9,full_host_activity=True,
                input_transition_charge_c=.3e-12,block_write_cap_f=caps['wr_clk'],
                block_read_cap_f=caps['rd_clk'],block_clock_coupling=1.)))
            for coupling,offset in ((.1,-48000.),(.1,0.),(.1,48000.),(.25,0.))]
        base=next(imp for label,offset,imp in cases if label=='combined_clock_0.1' and offset==0.)
        cases += [('combined_no_converter_jitter',0.,dict(base,converter_clock_config={})),
                  ('combined_no_detector_phase',0.,dict(base,lo_config=dict(combined_lo_config,detector_phase_tones=()))),
                  ('combined_no_fifo_clock_charge',0.,dict(base,rail_config=dict(base['rail_config'],block_clock_coupling=0.))),
                  ('combined_no_additive_noise',0.,dict(base,noise_rms=0.,frontend_noise_rms=0.)),
                  ('combined_no_residual_phase',0.,dict(base,phase_rms_rad=0.)),
                  ('combined_no_oscillator_noise',0.,dict(base,lo_config=dict(combined_lo_config,noise_tones=())))]
    if pulse_clock_config is not None:
        cases.append(('pulse_complete_load',0.,dict(noise_budget(.2,12),
            pulse_clock_config=pulse_clock_config,
            converter_clock_config=dict(absolute_time=True,jitter_amplitude_s=pulse_converter_jitter_s),
            host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
            rail_config=rf_demonstration_rail(pulse_bias_current_a))))
    if case_labels is not None:
        if not case_labels or set(case_labels)-{row[0] for row in cases}:raise ValueError('Unknown HE20 cases')
        cases=[row for row in cases if row[0] in case_labels]
    if pulse_clock_config is not None and any(label!='pulse_complete_load' for label,_,_ in cases):
        raise ValueError('Select pulse_complete_load explicitly to preserve one absolute source epoch')
    noise=noise_budget(.2,12)
    whole=SampledRFStream(settings,**noise);parts=SampledRFStream(settings,**noise)
    assert np.array_equal(whole.process(train),np.r_[parts.process(train[:17]),parts.process(train[17:])])
    for label,offset,impairments in cases:
        cache_key=json.dumps([settings,impairments,transport_allocation,remote_clock_ppm,external_launch_s,remote_fault,external_substeps,offset,
            hashlib.sha256(samples.tobytes()).hexdigest()],sort_keys=True)
        cached=capture_cache is not None and cache_key in capture_cache
        try:
            if cached:
                observed,transport=copy.deepcopy(capture_cache[cache_key])
            else:
                observed,transport=live_host_rf_observation(local_samples,settings,host_mode=0,
                    transport_allocation=transport_allocation,offset_hz=offset,**source_options,**impairments)
        except LiveRFTransportFailure as error:
            results.append(dict(comparison=label,impairments=impairments,offset_hz=offset,
                transport=error.report,acquired=False,reason=str(error),conditional_quality_pass=False,
                receiver_delivery=dict(qualified=False,payload_bits=[],reason='transport_fault')))
            continue
        try:
            _,coarse=acquire_live_prefix(observed,known,fs)
            acquisition_filter=coarse['filter_samples'];raw_failure=coarse['raw_failure']
            corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
            at=acquisition['start']+len(known)+128+2*np.arange(len(train)+len(payload))
            recovered=(windowed_sinc_samples(corrected,at) if receiver_sinc else
                np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag))
            rate_fit=None
            if training_rate:
                rate_fit=training_clock_rate(train,recovered[:len(train)],256,wave.metadata['cp'],wave.metadata['data'])
                at=acquisition['start']+len(known)+128+2*np.arange(len(train)+len(payload))/(1+rate_fit['rate_error_ppm']*1e-6)
                recovered=(windowed_sinc_samples(corrected,at) if receiver_sinc else
                    np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag))
            eq=TrainedBlockEqualizer(256,wave.metadata['cp'],np.asarray(wave.metadata['data'])%256,channel_delays=channel_delays)
            pilots=TrainedBlockEqualizer(256,wave.metadata['cp'],np.asarray(wave.metadata['pilots'])%256)
            eq.train(train,recovered[:len(train)]);pilots.train(train,recovered[:len(train)])
            response=eq.response.copy()
            pilot_observed=pilots.observe(recovered[len(train):])
            raw_data=eq.observe(recovered[len(train):])
            if pilot_timing:
                data,pilot_corrected,phase_fit=pilot_timing_correct(raw_data,pilot_observed,
                    wave.metadata['data'],wave.metadata['pilots'])
                phase=phase_fit[:,0]
            else:
                data,phase=pilot_phase_correct(raw_data,pilot_observed)
                pilot_corrected=pilot_observed*np.exp(-1j*phase[:,None]);phase_fit=None
            pilot_quality=known_pilot_quality(pilot_corrected,pilots.spectrum(train)[0])
            # This fixture's BPSK levels come from known training, never payload.
            amplitude=float(np.median(abs(eq.spectrum(train))))
            decision_phase_fit=None
            if decision_phase:
                data,decision_phase_fit=crossfit_constellation_phase(data,wave.metadata['data'],[-amplitude,amplitude])
            decision_quality=constellation_quality(data,[-amplitude,amplitude])
            receiver_bits=(data.real>0).astype(int).ravel().tolist()
            receiver_delivery=dict(qualified=decision_quality['accepts'],
                payload_bits=receiver_bits if decision_quality['accepts'] else [],
                scope='External BPSK packet holdback from fixed-constellation residual; integrity remains external')
            assert np.array_equal(response,eq.response)
        except ValueError as error:
            results.append(dict(comparison=label,impairments=impairments,offset_hz=offset,
                acquired=False,reason=str(error),conditional_quality_pass=False,
                receiver_delivery=dict(qualified=False,payload_bits=[],reason='receiver_rejected')))
            continue
        expected=eq.spectrum(payload)
        evm=float(np.linalg.norm(data-expected)/np.linalg.norm(expected))
        errors=int(np.count_nonzero((data.real>0).ravel()!=wave.symbols))
        if label=='minimal' and remote_fault is None:assert errors==0
        if offset==0 and not cached:
            chunked,report=live_host_rf_observation(local_samples,settings,host_mode=0,transport_allocation=transport_allocation,chunks=(17,transport['frames']-17),**source_options,**impairments)
            assert np.array_equal(chunked,observed) and report==transport
        if capture_cache is not None and not cached:capture_cache[cache_key]=copy.deepcopy((observed,transport))
        results.append(dict(comparison=label,impairments=impairments,offset_hz=offset,settings=settings,acquired=True,raw_acquisition_failure=raw_failure,acquisition_filter_samples=acquisition_filter,transport=transport,acquisition=acquisition,
            training_blocks=4,training_rate_fit=rate_fit,payload_blocks=4,payload_bits=len(wave.symbols),symbol_errors=errors,
            evm_rms=evm,
            magnitude_evm_rms=float(np.linalg.norm(abs(data)-abs(expected))/np.linalg.norm(expected)),
            phase_unit_evm_rms=float(np.linalg.norm(data/np.maximum(abs(data),1e-30)-expected/abs(expected))/math.sqrt(expected.size)),
            per_block_evm_rms=(np.linalg.norm(data-expected,axis=1)/np.linalg.norm(expected,axis=1)).tolist(),
            quality_budget=.1,conditional_quality_pass=errors==0 and evm<=.1,
            decision_phase_fit=(decision_phase_fit.tolist() if decision_phase_fit is not None else None),
            receiver_delivery=receiver_delivery,decision_quality=decision_quality,decision_accepts_quality_failure=decision_quality['accepts'] and evm>.1,
            minimum_channel_gain=float(np.min(abs(response))),pilot_phase_rad=phase.tolist(),pilot_timing_fit=(phase_fit.tolist() if phase_fit is not None else None),pilot_quality=pilot_quality,
            pilot_accepts_quality_failure=pilot_quality['accepts'] and evm>.1,
            pilot_rejects_quality_pass=not pilot_quality['accepts'] and evm<=.1))
        try:eq.train(train,np.zeros_like(train))
        except ValueError:pass
        else:raise AssertionError('Silent OFDM channel accepted')
        try:eq.observe(recovered[len(train):])
        except ValueError:pass
        else:raise AssertionError('Rejected OFDM retraining retained stale response')
    assert constellation_quality(np.array([-1.,1.,-1.]),[-1.,1.])['accepts']
    assert not constellation_quality(np.zeros(8),[-1.,1.])['accepts']
    assert not constellation_quality(np.full(8,1.+.2j),[-1.,1.])['accepts']
    # A different valid word has zero residual; integrity remains external.
    assert constellation_quality(np.array([1.,-1.,1.]),[-1.,1.])['accepts']
    pilot_reference=np.ones(8,complex)
    assert known_pilot_quality(np.ones((4,8),complex),pilot_reference)['accepts']
    assert not known_pilot_quality(np.zeros((4,8),complex),pilot_reference)['accepts']
    for bad in (np.empty((0,8)),np.full((4,8),np.nan)):
        try:known_pilot_quality(bad,pilot_reference)
        except ValueError:pass
        else:raise AssertionError('Invalid pilots accepted as quality evidence')
    assessed=[row for row in results if 'pilot_quality' in row]
    pilot_assessment=dict(cases=len(assessed),payload_quality_failures=sum(row['evm_rms']>.1 for row in assessed),
        missed_quality_failures=sum(row['pilot_accepts_quality_failure'] for row in assessed),
        rejected_quality_passes=sum(row['pilot_rejects_quality_pass'] for row in assessed),
        used_as_readiness_gate=False,
        scope='Receiver-visible pilots only; agreement with offline payload scoring is finite evidence, not a universal detector guarantee or calibrated false-alarm rate.')
    if remote_fault is None:
        assert all(row['conditional_quality_pass'] for row in results if row['comparison'] in ('minimal','declared_noise'))
    excess=[row for row in results if row['comparison']=='excess_noise']
    if excess:assert all(not row['conditional_quality_pass'] for row in excess)
    return dict(pulse_bias_current_a=pulse_bias_current_a,electrical_budget=electrical_budget,electrical_reference_plane=electrical,transport_allocation=transport_allocation,external_launch_s=external_launch_s,remote_clock_ppm=remote_clock_ppm,external_substeps=external_substeps,payload_seed=payload_seed,frontend_input_referred=frontend_input_referred,channel_delays=(list(channel_delays) if channel_delays is not None else None),decision_phase=decision_phase,remote_fault=remote_fault,pilot_timing=pilot_timing,receiver_sinc=receiver_sinc,training_rate=training_rate,cases=results,pilot_proxy_assessment=pilot_assessment,noise_chunk_invariant=True,excess_noise_fails=(True if excess else None),zero_offset_chunk_invariant=True,rejected_training_invalidates_equalizer=True,
        scope='Live host/DAC/filter/mixer/ADC/host HE20 BPSK fixture with diagnostic chirp acquisition, independently known OFDM training and pilot phase correction. No standard Wi-Fi preamble, FEC, higher QAM or full frontend/phase-noise budget qualification; optional independent remote timing remains a finite diagnostic.')


def connected_phase_payload(transport_allocation='exclusive'):
    """External EDR/OQPSK fixtures through the same live RF/host composition."""
    fs=20e6
    known=diagnostic_chirp_prefix(fs)
    settings=dict(sample_hz=fs,tx_cutoff_hz=10e6,rx_cutoff_hz=5e6,rx_filter_order=5,converter_bits=12)
    results=[]
    for name,variant in [('bluetooth_br_edr','edr2'),('bluetooth_br_edr','edr3'),('ieee802154_24','')]:
        wave=fixture(name,variant,seed=951)
        payload=wave.samples*.2/np.sqrt(np.mean(abs(wave.samples)**2))
        samples=np.r_[np.zeros(73),known,np.zeros(128),payload,np.zeros(128)]
        cases=[('minimal',offset,{}) for offset in (-48000.,0.,48000.)]
        cases += [('declared_noise',offset,declared_rf_noise(.2,12)) for offset in (-48000.,0.,48000.)]
        for label,offset,impairments in cases:
            observed,transport=live_host_rf_observation(samples,settings,host_mode=0,transport_allocation=transport_allocation,offset_hz=offset,**impairments)
            try:_,coarse=acquire_live_prefix(observed,known,fs)
            except ValueError as error:
                results.append(dict(fixture=name,variant=variant,comparison=label,offset_hz=offset,
                    acquired=False,reason=str(error),conditional_quality_pass=False))
                continue
            corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
            at=acquisition['start']+len(known)+128+np.arange(len(payload))
            recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
            errors=int(np.count_nonzero(decisions(wave,recovered)!=wave.symbols))
            evm=float(np.sqrt(np.mean(abs(recovered-payload)**2)/np.mean(abs(payload)**2)))
            changed=observed.copy();changed[coarse['start']+len(known):]=0
            _,check=refine_chirp_prefix(changed,known,fs,coarse);assert check==acquisition
            if label=='minimal':assert errors==0
            if name=='ieee802154_24' and offset==0:
                chunked,report=live_host_rf_observation(samples,settings,host_mode=0,transport_allocation=transport_allocation,chunks=(17,transport['frames']-17),**impairments)
                assert np.array_equal(chunked,observed) and report==transport
            results.append(dict(fixture=name,variant=variant,comparison=label,impairments=impairments,acquired=True,coarse_acquisition=coarse,offset_hz=offset,settings=settings,
                transport=transport,acquisition=acquisition,symbols=len(wave.symbols),symbol_errors=errors,
                evm_rms=evm,quality_budget=.1,conditional_quality_pass=errors==0 and evm<=.1))
    assert all(row['conditional_quality_pass'] for row in results)
    return dict(transport_allocation=transport_allocation,cases=results,prefix_fit_payload_independent=True,oqpsk_zero_offset_chunk_invariant=True,
        scope='Known diagnostic chirp prefix, not standard Bluetooth/802.15.4 packet acquisition. EDR differential symbols and OQPSK chips observed independently from delivered host samples. No independent remote clock, sensitivity or blocker qualification.')


def common_reference_recovery_probe(progress=None):
    """Slow constant-drive lifecycle diagnostic with unchanged count windows.

    Explicit external loss/stop/rearm actions; no automatic detection, packet
    quality, mapped host-clock load or physical training-generation claim.
    """
    from oscillator_noise import FrequencyNoise
    from bit_event_codec import TrainedRecordReceiver
    from stream_codec import Receiver
    settings=dict(sample_hz=10e6,tx_cutoff_hz=2.5e6,rx_cutoff_hz=1.25e6,rx_filter_order=5,converter_bits=12,rx_gain=1.)
    chip=BehavioralChip(Assumptions());chip.configure_numeric(engine='rf',rf=settings);chip.configure_transport('exclusive')
    chip.attach_shared_rail(inductance_h=5e-9,full_host_activity=True,input_transition_charge_c=.3e-12)
    clock=RailDrivenPulsePLL(rate_hz=2437000000,bandwidth_hz=1e6,fast_fraction=.1,require_acquisition=True)
    clock.set_noise(0.,FrequencyNoise.seeded(100000.,seed=831));chip.shared_rail.attach_pulse_clock(clock)
    chip.attach_rf_stream(lambda i:.25+.125j,external_substeps=4);core=chip.rf_stream
    chip.attach_pulse_rf(core);chip.attach_rf_timing(dict(absolute_time=True));chip.start()
    chip.advance(.0010001)
    assert clock.acquisition.acquired
    if progress is not None:progress(dict(stage='cold_acquired',time_s=chip.time))
    observer=TrainedRecordReceiver(decoder=Receiver(0,owner='iq'),startup_timeout_s=.002)
    received=[]
    def transfer():
        for i,word in enumerate(observer.training):observer.feed(word,chip.time-(8-i)/250e6)
        def emitted(at,word):
            received.extend(value for kind,value in observer.feed(word,at) if kind=='iq')
        report=chip.transfer(mode=0,source_hz=10e6,sample_bits=24,frames=8,
            epoch=chip.epoch,tx_source=lambda i:0,host_word_observer=emitted,**chip.timed_rf_callbacks())
        assert received==chip.stream['rx_words'] and len(received)*10==report['returned_bits']
        return report
    first=transfer();assert first['fault'] is None
    chip.set_common_reference(False);discarded=chip.stop();count=core.index;events=chip.shared_rail.converter_events
    observer.advance(observer.deadline());assert observer.fault=='Host clock timeout'
    rejected_words=len(received);received.clear()
    try:observer.feed(0,observer.time+4e-9)
    except ValueError:pass
    else:raise AssertionError('Faulted external receiver accepted stale traffic')
    chip.advance_reference_gap(chip.time+250e-9,maximum_step_s=100e-9)
    chip.set_common_reference(True);returned=chip.time
    for i in range(1,7):
     chip.advance_reference_gap(returned+i*250e-6,maximum_step_s=100e-9)
     if progress is not None:progress(dict(stage='recovery',step=i,measurements=clock.acquisition.measurements,acquired=clock.acquisition.acquired))
    assert core.index==count and chip.shared_rail.converter_events==events
    # Ensure a full third window, accounting for the first post-return anchor edge.
    chip.advance_reference_gap(chip.time+100e-9,maximum_step_s=100e-9)
    rearm=chip.rearm_after_reference();observer.arm(chip.time);chip.resume_rf_stream(lambda i:.25+.125j);chip.start();chip.advance(chip.ready_at)
    second=transfer();assert second['fault'] is None;assert chip.rf_stream is core
    result=dict(external_receiver=dict(discarded_words=rejected_words,resumed_words=len(received),explicit_retraining=True,physical_training_generation=False),first=first,discarded=discarded,reference_return_s=returned,rearm=rearm,second=second,retained_core=True,samples_at_gap=count,samples_after=core.index,clock_phase_cycles=clock.phase,scope='Constant-drive lifecycle smoke; default count windows and seeded PLL noise. No packet-quality or physical training-generation claim.')
    return result


def shared_pulse_rf_probe(contract,*,configuration_id='bluetooth_le_2m_20000000.0',
                          host_coupling=.1,lo_hz_per_v=10e6,noise_seed=831,
                          wait_for_acquisition=False,external_launch_s=20e-6+37e-9,
                          capture_tail_samples=128):
    """Reproducible external RX load screen; no chip protocol selection.

    Fixed startup is diagnostic unless count-qualified waiting is requested.
    External launch remains caller-owned, never derived from acquisition.
    Keep mapped FIFO clock loads so sensitivity comparisons are matched.
    """
    cases=[row for row in contract['behavioral_configuration_cases'] if row['id']==configuration_id]
    if len(cases)!=1:raise ValueError('Exactly one external numeric recipe required')
    caps=json.loads((P/'evidence/block-fifo-mapping.json').read_text())['clock_pin_load']['clock_pin_capacitance_f']
    return connected_numeric_gfsk(dict(contract,behavioral_configuration_cases=cases),
        matched_prefix=True,external_clock_ppm=0.,external_launch_s=external_launch_s,
        capture_tail_samples=capture_tail_samples,
        carrier_offsets_hz=(0.,),physical_options=dict(
            pulse_clock_config=dict(rate_hz=2437000000,bandwidth_hz=1e6,
                fast_fraction=.1,noise_rms_hz=100000.,noise_seed=noise_seed,
                require_acquisition=wait_for_acquisition,wait_for_acquisition=wait_for_acquisition),
            rail_config=dict(host_coupling=host_coupling,lo_hz_per_v=lo_hz_per_v,
                inductance_h=5e-9,full_host_activity=True,input_transition_charge_c=.3e-12,
                block_write_cap_f=caps['wr_clk'],block_read_cap_f=caps['rd_clk']),
            converter_clock_config=dict(absolute_time=True,jitter_amplitude_s=.5e-9),
            host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37))


def connected_numeric_gfsk(contract,matched_prefix=False,transport_allocation='exclusive',*,external_clock_ppm=None,physical_options=None,payload_symbols=64,carrier_offsets_hz=(-48000.,0.,48000.),capture_cache=None,external_substeps=16,external_launch_s=37e-9,capture_tail_samples=128,local_substeps=0):
    """Exercise actual contract settings; labels stay in this external fixture."""
    if type(local_substeps) is not int or not 0<=local_substeps<=64:raise ValueError('Local quadrature subdivisions must be 0 through 64')
    if local_substeps and external_clock_ppm is not None:raise ValueError('Local quadrature cannot select an independent source')
    if type(capture_tail_samples) is not int or capture_tail_samples<0:raise ValueError('Nonnegative capture tail required')
    if not math.isfinite(external_launch_s) or external_launch_s<0:raise ValueError('Finite nonnegative external launch time required')
    if external_clock_ppm is not None and (not math.isfinite(external_clock_ppm) or external_clock_ppm<=-1e6):raise ValueError("Finite positive remote clock rate")
    if type(payload_symbols) is not int or payload_symbols<1:raise ValueError('Positive integer payload length')
    carrier_offsets_hz=tuple(carrier_offsets_hz)
    if not carrier_offsets_hz or not all(math.isfinite(v) for v in carrier_offsets_hz):raise ValueError('Finite carrier offsets')
    physical_options=dict(physical_options or {})
    allowed={'lo_config','pulse_clock_config','rail_config','converter_clock_config','host_block_words','host_cdc_read_hz','host_cdc_phase','mixer_phase_source','startup_ready','startup_deadline_s','host_word_observer'}
    if set(physical_options)-allowed:raise ValueError('Unknown coupled observation setting')
    results=[]
    for case in contract['behavioral_configuration_cases']:
        name=case.get('fixture');variant=case.get('variant','')
        if name not in ('bluetooth_le','proprietary_gfsk') and not (name=='bluetooth_br_edr' and variant=='br'):continue
        settings=validate_rf_settings(**case['rf']);fs=settings['sample_hz']
        wave=(gfsk(np.random.default_rng(951).integers(0,2,64),rate=case['symbol_rate_hz'])
              if name=='proprietary_gfsk' else fixture(name,variant,seed=951))
        if payload_symbols!=64:
            wave=gfsk(np.random.default_rng(951).integers(0,2,payload_symbols),
                rate=wave.metadata['symbol_rate'],h=wave.metadata['h'],fs=wave.sample_hz)
        indices=np.minimum((np.arange(math.ceil(wave.duration*fs))*wave.sample_hz/fs).astype(int),len(wave.samples)-1)
        payload=.2*wave.samples[indices]
        bandwidth=(max(b for b in (203125.,406250.,812500.,1625000.) if b<=settings['rx_cutoff_hz']/2)
                   if matched_prefix else 1625000.)
        known=diagnostic_chirp_prefix(fs,bandwidth=bandwidth)
        samples=np.r_[np.zeros(73),known,np.zeros(128),payload,np.zeros(capture_tail_samples)]
        impairments=declared_rf_noise(.2,settings['converter_bits'])
        remote=dict(external_substeps=local_substeps);drive=samples
        if external_clock_ppm is not None:
            timeline=np.arange(len(samples))
            def remote_source(time):
                at=(time-external_launch_s)*fs*(1+external_clock_ppm*1e-6)
                return (np.interp(at,timeline,samples.real,left=0,right=0)
                        +1j*np.interp(at,timeline,samples.imag,left=0,right=0))
            remote=dict(receive_source=remote_source,external_substeps=external_substeps)
            drive=np.zeros_like(samples)
        for offset in carrier_offsets_hz:
            try:
                observed,transport=live_host_rf_observation(drive,settings,host_mode=0,transport_allocation=transport_allocation,offset_hz=offset,**physical_options,**remote,**impairments)
            except LiveRFTransportFailure as error:
                observed=np.array([],complex);transport=error.report
            row=dict(local_substeps=local_substeps,capture_tail_samples=capture_tail_samples,external_launch_s=external_launch_s,external_substeps=external_substeps,external_clock_ppm=external_clock_ppm,configuration=case['id'],settings=settings,prefix_bandwidth_hz=bandwidth,offset_hz=offset,impairments=impairments,
                     transport=transport,quality_budget=.1)
            if transport['stage']!='transport' or transport['flow'].get('fault'):
                results.append(dict(row,acquired=False,reason='Transport/clock interrupted',conditional_quality_pass=False));continue
            if capture_cache is not None:
                capture_cache[(case['id'],offset)]=dict(observed=observed.copy(),known=known.copy(),sample_hz=fs)
            try:
                _,coarse=acquire_live_prefix(observed,known,fs)
                corrected,acquisition=refine_chirp_prefix(observed,known,fs,coarse)
            except ValueError as error:
                results.append(dict(row,acquired=False,reason=str(error),conditional_quality_pass=False));continue
            at=acquisition['start']+len(known)+128+np.arange(len(wave.samples))*fs/wave.sample_hz
            if len(at)==0 or at[0]<0 or at[-1]>len(corrected)-1:
                results.append(dict(row,acquired=True,acquisition=acquisition,reason='Incomplete payload window',conditional_quality_pass=False));continue
            recovered=np.interp(at,np.arange(len(corrected)),corrected.real)+1j*np.interp(at,np.arange(len(corrected)),corrected.imag)
            receiver_quality=gfsk_decision_quality(recovered,fs=wave.sample_hz,
                symbol_rate_hz=wave.metadata['symbol_rate'],modulation_index=wave.metadata['h'])
            errors=int(np.count_nonzero(decisions(wave,recovered)!=wave.symbols))
            expected=.2*wave.samples
            evm=float(np.linalg.norm(recovered-expected)/np.linalg.norm(expected))
            # External diagnostic only: transmitted labels must never correct the
            # receiver or alter its acceptance decision. Orthogonal decomposition
            # distinguishes a constant complex scale from remaining distortion.
            energy=float(np.vdot(expected,expected).real)
            scalar=np.vdot(expected,recovered)/energy
            residual=recovered-scalar*expected
            residual_power=float(np.vdot(residual,residual).real/energy)
            constant_power=float(abs(scalar-1)**2)
            assert math.isclose(evm**2,constant_power+residual_power,rel_tol=1e-10,abs_tol=1e-12)
            diagnostic=dict(uses_payload_truth=True,used_for_acceptance=False,
                constant_complex_gain_real=float(scalar.real),constant_complex_gain_imag=float(scalar.imag),
                constant_error_power=constant_power,residual_error_power=residual_power,
                residual_evm_rms=math.sqrt(residual_power))
            results.append(dict(row,acquired=True,coarse_acquisition=coarse,acquisition=acquisition,
                symbols=len(wave.symbols),symbol_errors=errors,evm_rms=evm,
                receiver_quality=receiver_quality,error_decomposition=diagnostic,
                conditional_quality_pass=errors==0 and evm<=.1))
    if matched_prefix and external_clock_ppm is None and not physical_options and payload_symbols==64:assert all(row['conditional_quality_pass'] for row in results)
    return dict(payload_symbols=payload_symbols,physical_options=physical_options,transport_allocation=transport_allocation,cases=results,scope='Actual numeric GFSK configurations, independent selectable-length payload and shared diagnostic chirp prefix. Both finite host directions, declared additive/IID phase noise. Optional independent external envelope has a separately specified launch time, prescribed remote rate and selectable filter substeps; local DAC carries zero in that RX test. Not standard packet acquisition, aperture jitter or shared-supply closure.')


def fractional_rf_payload_probe(contract,*,carrier_hz=2412000000,
        bandwidth_hz=300000.,fast_fraction=.5,noise_rms_hz=100000.,
        noise_seed=830,external_substeps=16,payload_symbols=64,divider_order=2,configuration_id='bluetooth_le_1m_10000000.0',
        host_block_words=1,host_cdc_read_hz=None,host_cdc_phase=0.,
        converter_clock_config=None,external_launch_s=37e-9,capture_tail_samples=128,cold_global_clock=False,enforce_acquisition=False,wait_for_acquisition=False,startup_deadline_s=.002,oscillator_pull=None):
    """Focused external RX diagnostic; no acquisition or supply closure claim."""
    from shaped_fractional_pll import ShapedFractionalPLL,ThirdOrderFractionalPLL
    from oscillator_noise import FrequencyNoise
    if divider_order not in (2,3):raise ValueError('Supported diagnostic divider orders are 2 and 3')
    selected=copy.deepcopy(contract)
    selected['behavioral_configuration_cases']=[c for c in contract['behavioral_configuration_cases']
        if c['id']==configuration_id]
    if len(selected['behavioral_configuration_cases'])!=1:
        raise ValueError('Expected one existing numeric configuration')
    choice=selected['behavioral_configuration_cases'][0]
    if not (choice.get('fixture') in ('bluetooth_le','proprietary_gfsk') or
            (choice.get('fixture')=='bluetooth_br_edr' and choice.get('variant')=='br')):
        raise ValueError('This diagnostic currently requires a GFSK configuration')
    pll_class=ShapedFractionalPLL if divider_order==2 else ThirdOrderFractionalPLL
    pll=pll_class(rate_hz=carrier_hz,bandwidth_hz=bandwidth_hz,
                           fast_fraction=fast_fraction)
    pll.frequency_noise=FrequencyNoise.seeded(noise_rms_hz,seed=noise_seed)
    if type(cold_global_clock) is not bool or type(enforce_acquisition) is not bool:raise ValueError('Boolean clock selections required')
    if type(wait_for_acquisition) is not bool:raise ValueError('Boolean startup wait selection required')
    if wait_for_acquisition and not enforce_acquisition:raise ValueError('Startup wait requires active acquisition interlock')
    if enforce_acquisition and not cold_global_clock:raise ValueError('Acquisition interlock requires cold global clock')
    if cold_global_clock and not (converter_clock_config or {}).get('absolute_time',False):
        raise ValueError('Cold global PLL requires absolute converter timestamps')
    # Historical diagnostic keeps its explicit warm offset. Cold mode evolves
    # from zero on the converter's global axis, without rebasing oscillator phase.
    if not cold_global_clock:assert pll.advance(39e-6)
    initial=pll.phase
    epoch=0. if cold_global_clock else 40e-6
    phase_origin=0. if cold_global_clock else 1e-6
    from fractional_pulse_screen import CountedAcquisition
    acquisition=CountedAcquisition(carrier_hz) if cold_global_clock else None
    first_acquired=None;query_count=0;unqualified_queries=0
    pull_pending=None
    if oscillator_pull is not None:
        pull_pending=tuple(oscillator_pull)
        if (len(pull_pending)!=4 or not all(math.isfinite(v) for v in pull_pending)
                or pull_pending[0]<pll.time or pull_pending[2]<=0):
            raise ValueError('Pull requires future time, voltage, positive decay and sensitivity')
    pull_applied=None
    def advance_segment(target):
        nonlocal first_acquired
        if acquisition is not None:
            while pll.next_reference<=target:
                if not pll.advance(pll.next_reference):
                    raise ClockQualificationError('Pulse PLL left its compliance envelope')
                acquisition.reference_edge(pll.time,math.floor(pll.phase/16))
                if acquisition.acquired and first_acquired is None:first_acquired=pll.time
        if not pll.advance(target):raise ClockQualificationError('Pulse PLL left its compliance envelope')
        if acquisition is not None:acquisition.tick(target)
    def advance_clock(target):
        nonlocal pull_pending,pull_applied
        if pull_pending is not None and pull_pending[0]<=target:
            advance_segment(pull_pending[0])
            before=(pll.phase,pll.filter.v,pll.filter.w)
            pll.set_supply(*pull_pending)
            assert before==(pll.phase,pll.filter.v,pll.filter.w)
            pull_applied=pull_pending;pull_pending=None
        advance_segment(target)
    def startup_ready(time):
        advance_clock(time)
        return acquisition.acquired
    def phase(times):
        nonlocal query_count,unqualified_queries
        values=[]
        for t in times:
            advance_clock(epoch+float(t))
            if acquisition is not None:
                query_count+=1;unqualified_queries+=int(not acquisition.acquired)
                if enforce_acquisition and not acquisition.acquired:
                    raise ClockQualificationError('Prescaled count acquisition incomplete')
            values.append(-2*math.pi*(pll.phase-initial-carrier_hz*(t+phase_origin)))
        return np.asarray(values)
    row=connected_numeric_gfsk(selected,matched_prefix=True,external_clock_ppm=0.,
        carrier_offsets_hz=(0.,),physical_options=dict(mixer_phase_source=phase,
            host_block_words=host_block_words,host_cdc_read_hz=host_cdc_read_hz,host_cdc_phase=host_cdc_phase,
            converter_clock_config=converter_clock_config,
            startup_ready=startup_ready if wait_for_acquisition else None,startup_deadline_s=startup_deadline_s),
        external_launch_s=external_launch_s,external_substeps=external_substeps,payload_symbols=payload_symbols,
        capture_tail_samples=capture_tail_samples)['cases'][0]
    return dict(oscillator_pull_applied=pull_applied,cold_global_clock=cold_global_clock,divider_order=divider_order,carrier_hz=carrier_hz,bandwidth_hz=bandwidth_hz,
        fast_fraction=fast_fraction,noise_rms_hz=noise_rms_hz,noise_seed=noise_seed,
        phase_substeps=external_substeps,payload_symbols=payload_symbols,case=row,loop_filter=pll.filter.metrics(),
        counted_acquisition=(None if acquisition is None else dict(
            acquired=acquisition.acquired,first_acquired_s=first_acquired,
            completed_windows=acquisition.measurements,mixer_queries=query_count,
            unqualified_mixer_queries=unqualified_queries,
            interlock_applied=enforce_acquisition,
            scope='Same live PLL edge counts; optional fail-closed conversion interlock, not phase-quality qualification.')),
        scope='Persistent actual fractional PLL drives independent RX mixer; selectable converter time axis, local DAC zero, optional count-acquisition interlock, no shared rail. Not TX or standard packet qualification.')


def connected_gfsk_payload(bits=12):
    if bits not in (8,12):raise ValueError('Supported converter precision required')
    mode=1 if bits==8 else 0
    prefix=np.random.default_rng(913).integers(0,2,32)
    payload=np.random.default_rng(37).integers(0,2,64)
    wave=gfsk(np.r_[prefix,payload],fs=20e6)
    known_prefix=gfsk(prefix,fs=20e6)
    settings=dict(sample_hz=20e6,tx_cutoff_hz=10e6,rx_cutoff_hz=2.5e6,rx_filter_order=5,converter_bits=bits)
    samples=np.r_[np.zeros(73),wave.samples*.2,np.zeros(128)]
    results=[]
    for offset in (-48000.,0.,48000.):
        observed,transport=live_host_rf_observation(samples,settings,offset_hz=offset)
        flow=transport['flow']
        start,score=acquire_gfsk_prefix(observed,known_prefix)
        decoded=decisions(wave,observed[start:start+len(wave.samples)])[len(prefix):]
        errors=int(np.count_nonzero(decoded!=payload))
        assert errors==0
        try:acquire_gfsk_prefix(np.zeros_like(observed),known_prefix)
        except ValueError:pass
        else:raise AssertionError('Silent packet acquired')
        results.append(dict(converter_bits=bits,host_mode=mode,offset_hz=offset,flow=flow,symbols=len(payload),symbol_errors=errors,
            acquired_start=start,training_correlation=score,
            observation='Delivered host words only; bounded synthetic known-prefix acquisition, no standard packet claim'))
    return results


def usb_staged_response_trace(*,d2h_cdc=False,commit_beats=2,fused_d2h_snapshot=False,record_tail_bits=None):
    """Idle-boundary token through real codec and FIFO; not USB packet proof."""
    from stream_codec import encode,Receiver
    if type(commit_beats) is not int or not 0<=commit_beats<=2:
        raise ValueError("commit_beats must be 0, 1 or 2; reduced values are sensitivity probes")
    if record_tail_bits is not None and (type(record_tail_bits) is not int or not 0<=record_tail_bits<=30):
        raise ValueError("record_tail_bits must be an integer from 0 through 30")
    if fused_d2h_snapshot and not d2h_cdc:
        raise ValueError("Fused snapshot requires D2H crossing")
    def next_edge(t,period,origin=0.):
        # Same-edge publication misses the snapshot (conservative setup tie).
        return origin+(math.floor((t-origin)/period+1e-12)+1)*period
    def codec_event(mode,payload):
        decoder=Receiver(mode,frame_words=8);events=[]
        for slot,word in enumerate(encode(mode,payload,[],0,frame_words=8)):
            event=decoder.feed(word)
            if event and event[0]=='wire':events.append((slot,event[1]))
        assert [value for _,value in events]==payload
        return events
    def cross(payload,commit,write_period,read_period,read_origin):
        fifo=BlockFIFO()
        # Steady idle: reset release is complete, no queued traffic.
        for _ in range(3):fifo.step(wr_edge=True,rd_edge=True)
        wr_time=commit
        rd_time=read_origin+math.ceil((commit-read_origin)/read_period-1e-12)*read_period
        written=False;delivery=None;crossing=[]
        while delivery is None:
            now=min(wr_time,rd_time)
            wr=bool(abs(now-wr_time)<1e-18);rd=bool(abs(now-rd_time)<1e-18)
            before=fifo.status()
            result=fifo.step(wr_edge=wr,rd_edge=rd,
                words=payload if wr and not written else None,pop=True)
            if result['written']:written=True
            if result['read'] is not None:
                assert before['rd_valid'] and before['words']==payload
                assert result['read']==payload;delivery=now
            crossing.append(dict(time_s=now,write_edge=wr,read_edge=rd,
                accepted=result['written'],delivered=result['read'] is not None))
            if wr:wr_time+=write_period
            if rd:rd_time+=read_period
            assert len(crossing)<16
        assert 2*read_period-1e-15<=delivery-commit<=3*read_period+1e-15
        return delivery,crossing
    rows=[]
    for mode,hz in ((0,250e6),(1,312.5e6)):
        word=1/hz;frame=8*word;read_period=1/40e6
        incoming=codec_event(mode,[0x155]);outgoing=codec_event(mode,[0x12a,0x2a5,0x17])
        incoming_block=tuple(v for _,v in incoming);notice_slot=incoming[-1][0]
        if record_tail_bits is not None:
            from bit_event_codec import encode_records,StreamingRecordReceiver
            # Existing alternate raw-record interpretation. Data and the opaque
            # boundary are carried together; no invented USB opcode/recognizer.
            records=[];remaining=record_tail_bits
            while remaining:
                count=min(10,remaining)
                records.append(('data',(1<<count)-1,count,0.));remaining-=count
            records.append(('event',7,0,0.))
            incoming_block=tuple(encode_records(records,0))
            decoder=StreamingRecordReceiver();decoded=[];notice_slot=None
            for slot,value in enumerate(incoming_block):
                events=decoder.feed(value);decoded.extend(events)
                if any(event[0]=='event' for event in events):notice_slot=slot
            decoder.finish()
            assert decoded==[record[:3] for record in records]
            assert notice_slot==4+(record_tail_bits+9)//10
        worst=None;count=0;failures=0
        for event_phase in np.linspace(0,1,17):
            event_time=event_phase*frame
            for source_phase in (np.linspace(0,1,9,endpoint=False) if d2h_cdc else [0.]):
                for host_phase in np.linspace(0,1,17):
                    host_origin=host_phase*frame
                    # Retain declared packing/queue allowance, split equally.
                    source_ready=event_time+10/480e6+2*word
                    d2h_crossing=[];d2h_commit=None;d2h_delivery=source_ready
                    if d2h_cdc:
                        # Candidate: source publishes on a 40 MHz edge; host reads
                        # at its frame rate. Snapshot cannot consume same-edge data.
                        d2h_commit=next_edge(source_ready,read_period,source_phase*read_period)
                        d2h_delivery,d2h_crossing=cross(incoming_block,
                            d2h_commit,read_period,frame,0.)
                    # FIFO read data/valid are present before the pop edge. Frame
                    # preparation can latch them on that edge; emission still waits
                    # a full frame. No post-edge pointer/data bypass is allowed.
                    rx_snapshot=d2h_delivery if fused_d2h_snapshot else next_edge(d2h_delivery,frame)
                    rx_emission=rx_snapshot+frame
                    receiver_notice=rx_emission+notice_slot*word
                    decision=receiver_notice+40e-9
                    tx_snapshot=next_edge(decision,frame,host_origin)
                    tx_emission=tx_snapshot+frame
                    collected=tx_emission+7*word
                    commit=collected+commit_beats*frame
                    for cdc_phase in np.linspace(0,1,9,endpoint=False):
                        delivery,crossing=cross(tuple(v for _,v in outgoing),commit,frame,
                                                  read_period,cdc_phase*read_period)
                        end=delivery+2*word+10/480e6+34e-9
                        latency=end-event_time;count+=1;failures+=int(latency>400e-9)
                        if worst is None or latency>worst['latency_s']:
                            worst=dict(latency_s=latency,event_s=event_time,rx_snapshot_s=rx_snapshot,
                                rx_emission_s=rx_emission,receiver_notice_s=receiver_notice,
                                fpga_decision_s=decision,tx_snapshot_s=tx_snapshot,tx_emission_s=tx_emission,
                                collected_s=collected,commit_s=commit,delivery_s=delivery,response_s=end,
                                event_phase=float(event_phase),host_phase=float(host_phase),cdc_phase=float(cdc_phase),
                                crossing=crossing,d2h_source_phase=float(source_phase),d2h_commit_s=d2h_commit,
                                d2h_delivery_s=d2h_delivery,d2h_crossing=d2h_crossing)
        bound=usb_framed_turnaround(word_hz=hz,h2d_commit_words=8*commit_beats,h2d_cdc_hz=40e6)
        if not d2h_cdc:assert worst['latency_s']<=bound['worst_s']+1e-15
        rows.append(dict(host_word_hz=hz,cases=count,over_budget_cases=failures,worst=worst,
            partial_bound_s=bound['worst_s'],budget_s=400e-9))
    if commit_beats==2:assert rows[0]['over_budget_cases']>0
    if d2h_cdc and not fused_d2h_snapshot:assert all(row['over_budget_cases']>0 for row in rows)
    return dict(cases=rows,d2h_cdc_candidate=d2h_cdc,commit_beats=commit_beats,
        reduced_commit_is_sensitivity_only=commit_beats!=2,
        fused_d2h_snapshot=fused_d2h_snapshot,record_tail_bits=record_tail_bits,
        incoming_boundary_slot=notice_slot,
        scope='Optional D2H candidate: 40 MHz source to host frame clock via the checked block FIFO, next-edge publication/snapshot. Generic boundary token and response prefix, actual short-frame codec and block FIFO, steady idle/no backlog. Assumed packing, queue, FPGA and analog delays retained. D2H is a candidate only when enabled; actual USB packet/EOP detection, command application and pad timing are not composed; no whole-chip turnaround qualification.')


def raw_host_alignment_controls(reference_gap=False,host_clock_gap=False,*,remote_clock_ppm=0.,host_clock_ppm=0.):
    """External alignment sees only serialized raw records and ordered status."""
    from bit_event_stream import BitEventStream
    if host_clock_gap:reference_gap=True
    if not all(math.isfinite(x) and abs(x)<=1000 for x in (remote_clock_ppm,host_clock_ppm)):
        raise ValueError('Finite wired and host clock errors within 1000 ppm required')
    line_rate=2.5e9*(1+remote_clock_ppm*1e-6)
    host_rate=312.5e6*(1+host_clock_ppm*1e-6)
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    payloads=np.random.default_rng(723).integers(0,2,(24,160)).tolist()
    framed=marker+[b for payload in payloads for b in payload+marker]
    rows=[]
    for gap in (0,1000,10000):
        bits=[0,1]*1020+framed+[0]*gap+framed+[0]*200
        raw=RecoveredWordSource(bits,line_rate,.35,100.)
        records=BitEventStream(128);host=TimedBulkRecordReturn(records,word_hz=host_rate,trained=host_clock_gap)
        gate=ObservedFrameAlignment(marker,160);released=[]
        source_good=False;fpga_good=False;now=0.;read_index=0;events=[]
        records.event(2,0.);source_events=[(0.,2)]
        monitor=ReferencePresence([i*25e-9 for i in range(1601)
            if not reference_gap or not 72<=i<96])
        reference_good=not reference_gap;monitor_index=0;discarded=[]
        reference_changes=[];restart_discards=[];cancelled_status=0;timeout_seen=False;cdr_at_stop=None;cdr_advanced_during_stop=0
        def observe(bit,good):
            nonlocal source_good
            if not host.clock_active:return
            good=good and reference_good
            if good!=source_good:
                records.event(1 if good else 2,now);source_events.append((now,1 if good else 2));source_good=good
            records.bit(bit,now)
        raw.bit_observer=observe
        def receive():
            nonlocal read_index,fpga_good,timeout_seen
            if host_clock_gap and host.receiver.fault is not None:
                if not timeout_seen:discarded.append(len(gate.pending or []))
                gate.invalidate();fpga_good=False;timeout_seen=True
            for arrival,(kind,value,count) in host.observed[read_index:]:
                if kind=='event':
                    if value not in (1,2):raise ValueError('Unknown timing status')
                    fpga_good=value==1;events.append((arrival,value))
                    if not fpga_good:
                        discarded.append(len(gate.pending or []));gate.invalidate()
                else:
                    for bit_index in range(count):
                        frame=gate.observe((value>>bit_index)&1,fpga_good)
                        if frame is not None:released.append(frame)
            read_index=len(host.observed)
        change_at=2040+len(framed)
        for index in range(len(bits)//10):
            if raw.bit_index<=change_at<raw.bit_index+10:raw.frequency+=100e-6
            timestamp=raw.forecast(index)
            # Independent watchdog edges precede any later recovered-word
            # commit. No queued record is reset, reordered or bypassed.
            if reference_gap:
                while monitor_index*monitor.tick<=timestamp:
                    now=monitor_index*monitor.tick;host.advance(now);receive()
                    present=monitor.qualified(now)
                    if present!=reference_good:
                        reference_good=present;reference_changes.append((now,present))
                        if host_clock_gap and not present:
                            host.halt(now);cdr_at_stop=raw.bit_index
                        elif host_clock_gap and present and not host.clock_active:
                            cancelled_status+=len(source_events)-len(events)
                            del source_events[len(events):]
                            before=(raw.bit_index,raw.phase,raw.correction,raw.frequency,raw.pending)
                            restart_discards.append(host.restart(now));source_good=False
                            assert before==(raw.bit_index,raw.phase,raw.correction,raw.frequency,raw.pending)
                            cdr_advanced_during_stop=raw.bit_index-cdr_at_stop
                            assert cdr_advanced_during_stop>0
                        good=present and raw.timing_qualified
                        if good!=source_good:
                            records.event(1 if good else 2,now);source_events.append((now,1 if good else 2));source_good=good
                    monitor_index+=1
            now=timestamp;host.advance(now);receive();raw.consume(index)
        records.event(2,now);source_events.append((now,2));host.advance(now+10e-6);receive()
        assert [code for _,code in events]==[code for _,code in source_events]
        latencies=[arrival-sent for (arrival,_),(sent,_) in zip(events,source_events)]
        assert all(delay>=0 for delay in latencies)
        expected=iter(payloads+payloads)
        for frame in released:
            assert any(candidate==frame for candidate in expected),'Corrupt, duplicate or reordered payload'
        assert len(released)>=(32 if reference_gap else 44) and not fpga_good and gate.pending is None
        if reference_gap:
            assert [good for _,good in reference_changes]==[True,False,True]
            assert max(discarded)>0,'Reference loss did not exercise pending payload'
        if host_clock_gap:assert timeout_seen and len(restart_discards)==1
        rows.append(dict(cdr_bits_during_clock_stop=cdr_advanced_during_stop,host_clock_gap=host_clock_gap,timeout_seen=timeout_seen,restart_discards=restart_discards,cancelled_status=cancelled_status,reference_changes=reference_changes,discarded_candidate_bits=discarded,gap_bits=gap,released_frames=len(released),
            timing_events=len(events),maximum_status_latency_s=max(latencies),raw_bits=raw.bit_index,high_water=host.high_water,
            ordered_payload_identity=True))
    return dict(cases=rows,remote_clock_ppm=remote_clock_ppm,host_clock_ppm=host_clock_ppm,line_rate_bps=line_rate,host_word_hz=host_rate,alignment_after_host=True,
        scope='Persistent CDR/channel to raw bit/status packing, 84-bit bounded CDC, long frames and FPGA marker holdback. Word-atomic source publication; diagnostic markers, assumed CDR detector and unqualified physical host timing. Missing-reference pulses use an independent watchdog; the reference-only case retains host/publication clocks. Optional coordinated host/publication-clock halt and explicit digital flush/retraining preserve CDR evolution; management handshake/reset distribution and actual standard framing remain open.')


def staged_wired_duplex(*,remote_clock_ppm=100.,host_clock_ppm=-100.,chunks=(64,),reference_pacing=True,return_clock_gap=False,recover_tx=False,rearm_delay_s=0.,framed_rearm=False):
    """Finite simultaneous TX/RX composition; no autonomous clock claim."""
    from bit_event_stream import BitEventStream
    if type(framed_rearm) is not bool or (framed_rearm and not recover_tx):raise ValueError('Framed rearm requires recovery')
    if not math.isfinite(rearm_delay_s) or not 0<=rearm_delay_s<=100e-6 or (rearm_delay_s and not recover_tx):
        raise ValueError('Rearm delay requires recovery and must be within 0 to 100 us')
    if recover_tx and (not return_clock_gap or not reference_pacing):
        raise ValueError('TX recovery requires observed-clock loss with pacing')
    if not chunks or any(type(n) is not int or n<1 for n in chunks):raise ValueError('Positive frame chunks required')
    if not all(math.isfinite(v) and abs(v)<=1000 for v in (remote_clock_ppm,host_clock_ppm)):
        raise ValueError('Bounded independent clock errors required')
    chip=BehavioralChip(Assumptions(h2d_clock_scale=1+host_clock_ppm*1e-6))
    chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
    origin=chip.time;peer=EmittedWordChannel(residual_ppm=-100.)
    marker=np.random.default_rng(722).integers(0,2,64).tolist()
    tx_gate=ObservedFrameAlignment(marker,160);tx_packets=[]
    def observe_peer(bit,qualified):
        packet=tx_gate.observe(bit,qualified)
        if packet is not None:tx_packets.append(packet)
    if framed_rearm:peer.bit_observer=observe_peer
    payloads=np.random.default_rng(723).integers(0,2,(sum(chunks)*3+24+(600+math.ceil(rearm_delay_s*2.5e9/224) if recover_tx else 0),160)).tolist()
    bits=[0,1]*1020+marker+[b for packet in payloads for b in packet+marker]
    raw=RecoveredWordSource(bits,2.5e9*(1+remote_clock_ppm*1e-6),.35,100.)
    records=BitEventStream(128);host=TimedBulkRecordReturn(records,trained=return_clock_gap)
    gate=ObservedFrameAlignment(marker,160);released=[];read_index=0
    now=0.;source_good=False;fpga_good=False;pending_time=None
    controls=deque([(5e-6,'halt'),(5.6e-6,'restart')] if return_clock_gap else [])
    recovery=dict(enabled=return_clock_gap,timeout_observed=False,discarded=None,
                  cdr_bits_during_halt=0,frames_before_halt=0,frames_at_restart=0)
    stopped_bit=None;reference_tick_base=0;pacing_origin_ticks=0
    def observe(bit,good):
        nonlocal source_good
        if not host.clock_active:return
        if good!=source_good:records.event(1 if good else 2,now);source_good=good
        records.bit(bit,now)
    raw.bit_observer=observe
    def drain():
        nonlocal read_index,fpga_good
        if return_clock_gap and host.receiver.fault is not None:
            if not recovery['timeout_observed']:recovery['timeout_observed_s']=host.time
            recovery['timeout_observed']=True;fpga_good=False;gate.invalidate()
        for _,(kind,value,count) in host.observed[read_index:]:
            if kind=='event':
                fpga_good=value==1
                if not fpga_good:gate.invalidate()
            else:
                for n in range(count):
                    packet=gate.observe((value>>n)&1,fpga_good)
                    if packet is not None:released.append(packet)
        read_index=len(host.observed)
    def advance_rx(absolute):
        nonlocal now,pending_time,source_good,fpga_good,stopped_bit,reference_tick_base
        end=absolute-origin
        while True:
            if pending_time is None:pending_time=raw.forecast(raw.word_index)
            if controls and controls[0][0]<=min(end,pending_time):
                now,action=controls.popleft();host.advance(now);drain()
                if action=='halt':
                    host.halt(now);stopped_bit=raw.bit_index
                    recovery['frames_before_halt']=len(released)
                else:
                    state=(raw.bit_index,raw.phase,raw.correction,raw.frequency,raw.pending)
                    reference_tick_base+=host.clock_index
                    recovery['discarded']=host.restart(now)
                    assert state==(raw.bit_index,raw.phase,raw.correction,raw.frequency,raw.pending)
                    source_good=False;fpga_good=False;gate.invalidate()
                    recovery['cdr_bits_during_halt']=raw.bit_index-stopped_bit
                    recovery['frames_at_restart']=len(released)
                continue
            if pending_time>end:break
            now=pending_time;host.advance(now);drain();raw.consume(raw.word_index)
            pending_time=None
        host.advance(end);drain()
    def emit(time,word):
        advance_rx(time);peer.emit(time,word)
    def observed_ticks(time):
        advance_rx(time)
        return reference_tick_base+host.clock_index-pacing_origin_ticks
    source=lambda i:(37*i+5)%1024
    for frames in chunks:
        flow=chip.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=frames,
            epoch=chip.epoch,directions=('tx',),tx_source=source,host_block_words=8,
            host_cdc_read_hz=40e6,host_cdc_phase=.37,tx_word_observer=emit,
            tx_prefill_bits=1024,tx_reference_pacing=reference_pacing,
            tx_reference_ticks=observed_ticks if return_clock_gap and reference_pacing else None)
        if flow['fault'] is not None:break
    peer.advance(chip.time)
    assert peer.timing_qualified
    assert peer.words[200:]==chip.stream['tx_samples'][200:len(peer.words)]
    scored=max(0,len(peer.words)-200)
    initial_flow=flow;tx_word_errors=0;tx_frame_errors=None
    if recover_tx:
        assert flow['fault']=='underflow'
        old_epoch=chip.epoch;recovery['tx_discarded']=chip.stop()
        recovery['tx_stopped_s']=chip.time-origin
        before=len(released);before_bits=raw.bit_index
        chip.advance(chip.time+rearm_delay_s);advance_rx(chip.time)
        recovery['host_rearm_delay_s']=rearm_delay_s
        recovery['rx_frames_during_rearm_delay']=len(released)-before
        recovery['rx_bits_during_rearm_delay']=raw.bit_index-before_bits
        chip.start();chip.advance(chip.ready_at)
        # Explicit phase-aligned restart assumption, not a fabricated PLL lock.
        restart_word=math.ceil((chip.time-peer.origin)*peer.rate/10)
        restart_time=peer.origin+restart_word*10/peer.rate
        chip.advance(restart_time);advance_rx(restart_time)
        recovery['idle_bits']=peer.idle_until(restart_time)
        assert not peer.timing_qualified
        recovery['peer_lost_timing_during_idle']=True
        recovery['tx_restart_s']=restart_time-origin
        pacing_origin_ticks=reference_tick_base+host.clock_index
        next_source=lambda i:(53*i+17)%1024
        if framed_rearm:
            tx_payloads=np.random.default_rng(724).integers(0,2,(180,160)).tolist()
            framed_bits=[0,1]*1020+marker+[bit for packet in tx_payloads for bit in packet+marker]
            def next_source(index):
                return sum(bit<<j for j,bit in enumerate(framed_bits[10*index:10*index+10]))
        prefill=(1<<1024)-1
        args=dict(mode=1,source_hz=250e6,sample_bits=10,frames=64,
            directions=('tx',),tx_source=next_source,host_block_words=8,
            host_cdc_read_hz=40e6,host_cdc_phase=.37,tx_word_observer=emit,
            tx_prefill_bits=1024,tx_prefill_value=prefill,tx_reference_pacing=True,
            tx_reference_ticks=observed_ticks)
        try:chip.transfer(epoch=old_epoch,**args)
        except ValueError:recovery['stale_tx_epoch_rejected']=True
        else:raise AssertionError('Old TX epoch accepted')
        flow=chip.transfer(epoch=chip.epoch,**args)
        assert flow['fault'] is None
        advance_rx(chip.time);peer.advance(chip.time)
        assert peer.timing_qualified
        count=len(chip.stream['tx_samples'])
        expected_bits=prefill+sum(next_source(i)<<(1024+10*i) for i in range(count))
        expected_words=[(expected_bits>>(10*i))&1023 for i in range(count)]
        assert chip.stream['tx_samples']==expected_words,'Stale TX queue contents'
        observed=peer.words[restart_word+200:]
        expected_resumed=expected_words[200:200+len(observed)]
        tx_word_errors=sum(a!=b for a,b in zip(observed,expected_resumed))+abs(len(observed)-len(expected_resumed))
        if framed_rearm:
            recovery['raw_grouped_tx_word_errors']=tx_word_errors
            recovery['tx_recovered_frames']=len(tx_packets)
            tx_frame_errors=sum(packet!=expected for packet,expected in zip(tx_packets,tx_payloads))
            tx_frame_errors+=max(0,len(tx_packets)-len(tx_payloads))
            recovery['framed_payload_errors']=tx_frame_errors
            if not tx_packets:tx_frame_errors+=1
        assert len(observed)>1000
        recovery['tx_resumed_scored_words']=len(observed)
        scored+=len(observed)
    else:
        advance_rx(origin+sum(chunks)*64/312.5e6 if return_clock_gap else chip.time)
    if not return_clock_gap:assert flow['fault'] is None
    expected=iter(enumerate(payloads));indices=[]
    for packet in released:
        match=next((i for i,candidate in expected if candidate==packet),None)
        assert match is not None,'Corrupt, duplicate or reordered RX payload'
        indices.append(match)
    assert released
    if return_clock_gap:
        assert not controls and recovery['timeout_observed']
        assert recovery['cdr_bits_during_halt']>0 and recovery['frames_before_halt']>0
        assert len(released)>recovery['frames_at_restart']
        assert host.receiver.fault is None and host.receiver.locked
    else:assert released==payloads[:len(released)]
    return dict(framed_rearm=framed_rearm,reference_pacing=reference_pacing,remote_clock_ppm=remote_clock_ppm,h2d_clock_ppm=host_clock_ppm,
        elapsed_s=chip.time-origin,rx_elapsed_s=host.time,tx_emitted_words=peer.emitted_words,
        tx_scored_words=scored,tx_word_errors=tx_word_errors,
        rx_released_frames=len(released),rx_ordered=True,rx_payload_indices=indices,rx_high_water=host.high_water,recovery=recovery,
        duplex_recovered=flow['fault'] is None and (tx_frame_errors==0 if framed_rearm else tx_word_errors==0),
        tx_flow=flow,initial_tx_fault=initial_flow['fault'],rx_cdr_bits=raw.bit_index,
        scope='Simultaneous distinct H2D and D2H paths on one timeline, staged TX plus bounded bulk RX, independent line/H2D rates. Prescribed TX/host clocks, diagnostic guard/markers and channel; optional D2H/publication-clock timeout, actual observed-edge TX pacing and explicit RX flush/retraining; initial TX underflow is retained. Optional explicit TX stop/flush/new epoch, zero-differential idle and phase-aligned restart preserve peer CDR/channel. No serialized management handshake, arbitrary restart phase, physical idle pad, shared power, resource-ledger reconciliation or autonomous timing closure.')


class TimedBulkRecordReturn:
    """Raw records through 84-bit CDC, bounded staging and long host frames.

    Source service is 40 MHz; host preparation/CDC reads occur every eight
    host words. Two frame banks prevent same-edge CDC reads reaching output.
    These are mathematical schedules, not qualified physical timing.
    """
    def __init__(self,stream,word_hz=312.5e6,source_phase=0.,trained=False):
        from bit_event_stream import BitEventStream
        from bit_event_codec import StreamingRecordReceiver,TrainedRecordReceiver,encode_records
        from block_receiver_model import RecordBlockFIFO
        if not math.isfinite(word_hz) or word_hz<=0 or not math.isfinite(source_phase) or not 0<=source_phase<1:
            raise ValueError('Positive host rate and source phase in [0,1) required')
        self.stream=stream;self.staged=BitEventStream(67);self.fifo=RecordBlockFIFO()
        self.receiver=TrainedRecordReceiver(64) if trained else StreamingRecordReceiver(64)
        self.trained=trained;self.clock_active=True;self.origin=0.;self.clock_index=0
        self.training_index=0;self.epoch=0
        self.word_hz=word_hz;self.source_phase=source_phase
        self.source_index=self.word_index=0;self.next_source=source_phase/40e6
        self.frame=encode_records([],0,64);self.prepared=None;self.sequence=1
        self.time=0.;self.observed=[];self.high_water=[0,0,0];self.writes=self.reads=0

    def halt(self,time):
        if not self.trained:raise ValueError('Clock-loss testing requires trained receiver')
        self.advance(time);self.clock_active=False

    def restart(self,time,*,receiver_already_armed=False):
        from bit_event_codec import encode_records
        if not self.trained or self.clock_active:raise ValueError('Explicit halted-link restart required')
        self.advance(time)
        if receiver_already_armed and (self.receiver.fault is not None or self.receiver.locked or self.receiver.last_edge is not None):
            raise ValueError('Receiver must be armed before restart command application')
        discarded=dict(source_records=len(self.stream.records),partial_bits=self.stream.valid_bits,
            cdc_entries=(self.fifo.wb-self.fifo.rb)%16,staged_records=len(self.staged.records),
            prepared_frame=self.prepared is not None,emitting_position=self.word_index%64)
        self.stream.reset();self.stream.time=time;self.staged.reset();self.fifo.reset()
        self.frame=encode_records([],0,64);self.prepared=None;self.sequence=1
        self.source_index=self.word_index=self.clock_index=self.training_index=0
        self.origin=time;self.next_source=time+self.source_phase/40e6
        if not receiver_already_armed:self.receiver.arm(time)
        self.clock_active=True;self.epoch+=1
        return discarded

    def advance(self,time):
        from bit_event_codec import pack_record_block,unpack_record_block,snapshot_records
        if not math.isfinite(time) or time<self.time:raise ValueError('Return time')
        if not self.clock_active:
            self.receiver.advance(time);self.time=time;return
        if self.stream.fault:raise ValueError('Source stream fault requires reset')
        while min(self.next_source,self.origin+self.clock_index/self.word_hz)<=time:
            host_time=self.origin+self.clock_index/self.word_hz;now=min(self.next_source,host_time)
            source=abs(now-self.next_source)<1e-18;host=abs(now-host_time)<1e-18
            training=self.trained and self.training_index<len(self.receiver.training)
            read_edge=host and not training and self.word_index%8==0;block=None;take=0
            if source and not training and self.stream.records and self.fifo.status()['wr_ready']:
                records=list(self.stream.records);selected=[]
                if records[0][0]=='event':selected=records[:1]
                elif records[0][2]<10:
                    if len(records)<2 or records[1][0]!='event':raise ValueError('Partial word without boundary')
                    selected=records[:2]
                else:
                    for record in records[:8]:
                        if record[0]!='data' or record[2]!=10:break
                        selected.append(record)
                block=pack_record_block([r[:3] for r in selected]);take=len(selected)
            # Read acceptance uses pre-edge occupancy; no freed-space bypass.
            allow=len(self.staged.records)<=59
            if host and not training and self.word_index%64==0:
                if self.prepared is not None:self.frame=self.prepared
                self.prepared=snapshot_records(self.staged,self.sequence,64)
                self.sequence=(self.sequence+1)%64
            result=self.fifo.step(wr_edge=source,rd_edge=read_edge,words=block,pop=allow)
            if result['written']:
                for _ in range(take):self.stream.pop()
                self.writes+=1
            if result['read'] is not None:
                records=unpack_record_block(result['read'])
                self.staged._reserve(len(records))
                self.staged.records.extend((*r,now) for r in records);self.reads+=1
            if host:
                word=self.receiver.training[self.training_index] if training else self.frame[self.word_index%64]
                decoded=self.receiver.feed(word,now) if self.trained else self.receiver.feed(word)
                self.observed.extend((now,r) for r in decoded)
                if training:self.training_index+=1
                else:self.word_index+=1
                self.clock_index+=1
            if source:
                self.source_index+=1;self.next_source=self.origin+(self.source_index+self.source_phase)/40e6
            self.high_water=[max(a,b) for a,b in zip(self.high_water,
                (len(self.stream.records),(self.fifo.wb-self.fifo.rb)%16,len(self.staged.records)))]
        self.time=time


class TimedRecordReturn:
    """Candidate record frames across block CDC into continuous host framing.

    Source encoding on a 40 MHz publication edge is a functional assumption.
    The existing eight-entry FIFO and one host preparation frame remain explicit.
    Idle host frames advance host sequence independently of source sequence.
    """
    def __init__(self,stream,word_hz=250e6,source_phase=0.,coalesce=False):
        from bit_event_codec import StreamingRecordReceiver,encode_records
        if not math.isfinite(word_hz) or word_hz<=0 or not math.isfinite(source_phase) or not 0<=source_phase<1:
            raise ValueError('Positive host rate and source phase in [0,1) required')
        self.stream=stream;self.fifo=BlockFIFO();self.receiver=StreamingRecordReceiver()
        self.word_period=1/word_hz;self.source_period=1/40e6
        self.next_source=source_phase*self.source_period;self.word_index=0
        self.source_sequence=0;self.read_sequence=0;self.host_sequence=1
        self.frame=encode_records([],0);self.prepared=None
        self.observed=[];self.time=0.;self.writes=0;self.reads=0
        self.high_water=0;self.stalls=0;self.coalesce=coalesce;self.hold_one_edge=False
        # Warmed idle precondition; startup remains a separate required test.
        for _ in range(3):self.fifo.step(wr_edge=True,rd_edge=True)

    def advance(self,time):
        from bit_event_codec import snapshot_records,decode_records,encode_records
        if not math.isfinite(time) or time<self.time:raise ValueError('Return time')
        while True:
            host_time=self.word_index*self.word_period
            now=min(host_time,self.next_source)
            if now>time:break
            host=abs(now-host_time)<1e-18;source=abs(now-self.next_source)<1e-18
            frame_edge=host and self.word_index%8==0
            block=None
            if source and self.stream.records:
                if self.fifo.status()['wr_ready']:
                    # Avoid spending a whole CDC entry on one word during a
                    # continuous burst. Boundary bypasses aggregation; isolated
                    # data waits at most one additional source edge when ready.
                    enough=len(self.stream.records)>=2 or any(r[0]=='event' for r in self.stream.records)
                    if not self.coalesce or enough or self.hold_one_edge:
                        block=tuple(snapshot_records(self.stream,self.source_sequence))
                        self.source_sequence=(self.source_sequence+1)%64;self.hold_one_edge=False
                    else:self.hold_one_edge=True
                else:self.stalls+=1
            result=self.fifo.step(wr_edge=source,rd_edge=frame_edge,words=block,pop=True)
            if block is not None:assert result['written'];self.writes+=1
            if frame_edge:
                # Emit the bank prepared at the previous frame edge.
                if self.prepared is not None:self.frame=self.prepared
                records=[]
                if result['read'] is not None:
                    records=decode_records(list(result['read']),self.read_sequence)
                    self.read_sequence=(self.read_sequence+1)%64;self.reads+=1
                self.prepared=encode_records([(*r,now) for r in records],self.host_sequence)
                self.host_sequence=(self.host_sequence+1)%64
            if host:
                for record in self.receiver.feed(self.frame[self.word_index%8]):
                    self.observed.append((now,record))
                self.word_index+=1
            if source:self.next_source+=self.source_period
            self.high_water=max(self.high_water,(self.fifo.wb-self.fifo.rb)%16)
        self.time=time


class TimedRecordPlayback:
    """Eight-word collection, two commit beats, block CDC, raw serializer/pad."""
    def __init__(self,pad,word_hz=250e6,read_phase=0.,playback_capacity_bits=2048):
        from bit_event_stream import RawBurstPlayback
        from bit_event_codec import StreamingRecordReceiver
        if not math.isfinite(word_hz) or word_hz<=0 or not math.isfinite(read_phase) or not 0<=read_phase<1:
            raise ValueError('Positive host rate and read phase in [0,1) required')
        self.pad=pad;self.word_period=1/word_hz;self.frame_period=8*self.word_period
        self.receiver=StreamingRecordReceiver();self.player=RawBurstPlayback(capacity_bits=playback_capacity_bits)
        self.playback_peak_bits=0
        from collections import deque
        self.fifo=BlockFIFO();self.pending=deque()
        self.next_write=7*self.word_period;self.next_read=read_phase/40e6
        self.half_tick=0;self.time=0.;self.input_words=0;self.observed=[]
        self.first_drive=None;self.fault=None;self.writes=0;self.reads=0
        self.block_sequence=0;self.read_sequence=0;self.frame_records=[]
        for _ in range(3):self.fifo.step(wr_edge=True,rd_edge=True)

    def feed(self,word,time):
        from bit_event_codec import encode_records
        expected=self.input_words*self.word_period
        if abs(time-expected)>1e-15:raise ValueError('Continuous host word clock required')
        self.advance(time)
        if self.fault:raise ValueError(self.fault)
        try:
            self.frame_records.extend(self.receiver.feed(word))
            self.input_words+=1
            if self.input_words%8==0:
                if self.frame_records:
                    # Validated metadata and data travel atomically as one block.
                    frame=encode_records([(*r,time) for r in self.frame_records],self.block_sequence)
                    self.block_sequence=(self.block_sequence+1)%64
                    if len(self.pending)>=3:raise ValueError('Commit pipeline overflow')
                    self.pending.append((time+2*self.frame_period,tuple(frame)))
                self.frame_records=[]
        except ValueError as error:
            self.fault=str(error);self.pad.drive(peer=self.pad.peer);raise

    def advance(self,time):
        from bit_event_codec import decode_records
        if not math.isfinite(time) or time<self.time:raise ValueError('Playback time')
        while True:
            serial_time=self.half_tick/(2*480e6)
            now=min(self.next_write,self.next_read,serial_time)
            if now>time:break
            self.pad.advance(now)
            wr=abs(now-self.next_write)<1e-18;rd=abs(now-self.next_read)<1e-18
            serial=abs(now-serial_time)<1e-18
            try:
                # Serializer samples pre-edge queue state before coincident CDC.
                if serial:
                    if self.half_tick%2==0:
                        value=None if self.fault else self.player.tick()
                        self.pad.drive(local='Z' if value is None else ('J' if value else 'K'),peer=self.pad.peer)
                        if value is not None and self.first_drive is None:self.first_drive=now
                    elif not self.fault and self.pad.local!='Z':
                        observation=self.pad.observe();assert not observation['squelch']
                        self.observed.append((now,int(observation['j'])))
                block=None
                if wr and self.pending and self.pending[0][0]<=now+1e-18 and not self.fault:
                    _,block=self.pending.popleft()
                result=self.fifo.step(wr_edge=wr,rd_edge=rd,words=block,pop=not self.fault)
                if block is not None:
                    if not result['written']:raise ValueError('Playback crossing full')
                    self.writes+=1
                if result['read'] is not None:
                    records=decode_records(list(result['read']),self.read_sequence)
                    self.read_sequence=(self.read_sequence+1)%64;self.reads+=1
                    self.player.enqueue(records)
                    self.playback_peak_bits=max(self.playback_peak_bits,self.player.bits)
            except ValueError as error:
                self.fault=str(error);self.pad.drive(peer=self.pad.peer)
            if wr:self.next_write+=self.frame_period
            if rd:self.next_read+=1/40e6
            if serial:self.half_tick+=1
        self.time=time


def usb_observed_response(*,request_lengths=(23,61),split_time=False,usb_data_packet=False,packet_fault=None,retry_after_s=None,h2d_clock_ppm=0.,host_pacing=False,coalesce_return=False,clock_phases=((0.,0.),(.37,.37)),fpga_processing_s=40e-9,command_sync_cycles=0,fpga_ingress=None,playback_capacity_bits=2048,reference_pacing=False):
    """Pad burst to FPGA-derived reply through both candidate host directions."""
    from bit_event_stream import BitEventStream,SampledActivityBoundary
    from bit_event_codec import encode_records,ObservedClockPacer
    if not request_lengths or any(type(n) is not int or n<1 for n in request_lengths):
        raise ValueError('Positive integer request lengths required')
    if not math.isfinite(h2d_clock_ppm) or abs(h2d_clock_ppm)>1000:
        raise ValueError('Finite H2D clock error within 1000 ppm required')
    from protocol_pad import usb_hs_packet,usb_hs_decode_packet,USBStreamingPacket
    if type(reference_pacing) is not bool or (reference_pacing and not host_pacing):
        raise ValueError('Reference pacing requires enabled host pacing')
    if usb_data_packet and any(n%8 for n in request_lengths):raise ValueError('USB payload needs whole bytes')
    if packet_fault not in (None,'sync','pid','body','eop') or (packet_fault is not None and not usb_data_packet):
        raise ValueError('Packet faults require a supported USB fixture fault')
    if retry_after_s is not None and (packet_fault is None or not math.isfinite(retry_after_s) or retry_after_s<=400e-9):
        raise ValueError('Retry needs a damaged packet and a finite delay beyond the response window')
    if type(command_sync_cycles) is not int or not 0<=command_sync_cycles<=8:
        raise ValueError('Command synchronization cycles must be integer within 0 to 8')
    if not math.isfinite(fpga_processing_s) or not 0<=fpga_processing_s<=1e-6:
        raise ValueError('FPGA processing delay must be finite and within 0 to 1 us')
    requested_ingress=fpga_ingress
    host_clocked=fpga_ingress is not None and fpga_ingress.get('clock_source')=='host_ddr'
    if fpga_ingress is not None:
        if (set(fpga_ingress)-{'clock_hz','clock_source','bits_per_cycle','capacity_records','phase_cycles','synchronizer_cycles','decision_cycles'} or
            type(fpga_ingress.get('bits_per_cycle')) is not int or fpga_ingress['bits_per_cycle']<1):
            raise ValueError('Valid FPGA ingress settings and integer bits per cycle required')
        if host_clocked:
            if 'clock_hz' in fpga_ingress or fpga_ingress.get('phase_cycles',0.)!=0 or command_sync_cycles:
                raise ValueError('Host-clock parser uses derived clock, zero phase and synchronous response')
        elif (fpga_ingress.get('clock_source','independent')!='independent' or
              not math.isfinite(fpga_ingress.get('clock_hz',0.)) or fpga_ingress.get('clock_hz',0.)<=0):
            raise ValueError('Positive independent FPGA clock required')
        if 'decision_cycles' in fpga_ingress and (not host_clocked or type(fpga_ingress['decision_cycles']) is not int or not 1<=fpga_ingress['decision_cycles']<=16):
            raise ValueError('Explicit decision cycles require host-clocked pipeline and 1 to 16 cycles')
        phase=fpga_ingress.get('phase_cycles',0.)
        if not math.isfinite(phase) or not 0<=phase<1:raise ValueError('FPGA clock phase must be within [0,1)')
        stages=fpga_ingress.get('synchronizer_cycles',0)
        if type(stages) is not int or not 0<=stages<=8:raise ValueError('Synchronization cycles must be integer within 0 to 8')
        if 'capacity_records' in fpga_ingress and (not usb_data_packet or type(fpga_ingress['capacity_records']) is not int or fpga_ingress['capacity_records']<1):
            raise ValueError('Bounded ingress needs USB packet mode and positive record capacity')
    def ingress_visible(when):
        if fpga_ingress is None or not fpga_ingress.get('synchronizer_cycles',0):return when
        clock=fpga_ingress['clock_hz'];phase=fpga_ingress.get('phase_cycles',0.)
        # Candidate pointer/control visibility latency, not asynchronous sampling
        # of multibit data. Payload remains held in the bounded record storage.
        return (math.ceil(when*clock-phase-1e-9)+phase+fpga_ingress['synchronizer_cycles'])/clock
    def processing_ready(when,done):
        base=max(ingress_visible(when),done)
        if not host_clocked:return base+fpga_processing_s
        clock=fpga_ingress['clock_hz']
        cycles=fpga_ingress.get('decision_cycles',math.ceil(fpga_processing_s*clock-1e-9))
        return (math.ceil(base*clock-1e-9)+cycles)/clock
    rows=[]
    for hz in (250e6,312.5e6):
      for role in ('host','device'):
       for phase,read_phase in clock_phases:
        for request_length in request_lengths:
         pad=SharedWiredPad();pad.configure('usb',role,'hs',attached=True)
         source=BitEventStream(16);observer=SampledActivityBoundary(source)
         returned=TimedRecordReturn(source,word_hz=hz,source_phase=phase,coalesce=coalesce_return)
         h2d_hz=hz*(1+h2d_clock_ppm*1e-6)
         fpga_ingress=(dict(requested_ingress,clock_hz=h2d_hz/2,phase_cycles=0.) if host_clocked else requested_ingress)
         playback=TimedRecordPlayback(pad,word_hz=h2d_hz,read_phase=read_phase,playback_capacity_bits=playback_capacity_bits)
         request=np.random.default_rng(841).integers(0,2,request_length).tolist()
         request_bytes=bytes(sum(request[k+n]<<n for n in range(8)) for k in range(0,len(request),8)) if usb_data_packet else None
         levels=usb_hs_packet(0xc3,request_bytes) if usb_data_packet else usb_nrzi(request)
         if packet_fault is not None:
             index={'sync':0,'pid':35,'body':len(levels)-10,'eop':len(levels)-1}[packet_fault]
             levels[index]^=1
         ui=1/480e6;start=11*ui
         actions=[]
         for i,level in enumerate(levels):
             actions.extend([(start+i*ui,'drive',level),(start+(i+.5)*ui,'sample',None)])
         release=start+len(levels)*ui
         actions.append((release,'release',None))
         actions.extend((release+i*ui,'sample',None) for i in range(1,6))
         first_release=release;retry_state=None;rejections=[]
         if retry_after_s is not None:
             retry_start=first_release+retry_after_s
             clean=usb_hs_packet(0xc3,request_bytes)
             actions.append((retry_start,'retry',None))
             for i,level in enumerate(clean):
                 actions.extend([(retry_start+i*ui,'drive',level),(retry_start+(i+.5)*ui,'sample',None)])
             release=retry_start+len(clean)*ui
             actions.append((release,'release',None))
             actions.extend((release+i*ui,'sample',None) for i in range(1,6))
         ai=0;wi=0;seen=0;host_bits=[];decision=None;host_notice=None;fpga_ready=None
         response_records=[];response_payload=None;published=False;packet_rejection=None
         emitted=encode_records([],0);prepared=None;sequence=1
         detected=None;tokens=60.;token_time=None
         reference_pacer=ObservedClockPacer(480e6/(hz/2)) if reference_pacing else None
         packet_parser=USBStreamingPacket() if usb_data_packet else None
         ingress_done=0.;ingress_peak_work_s=0.;ingress_bits=0
         ingress_completions=[];ingress_peak_records=0;ingress_overflow=False
         word_limit=math.ceil((release+2.4*request_length/480e6+2e-6)*h2d_hz)
         if fpga_ingress is not None:
             # Observe slow processing through completion, retaining deadline
             # failure rather than truncating a still-pending response.
             word_limit+=math.ceil(len(levels)*(1+(retry_after_s is not None))*h2d_hz/fpga_ingress['clock_hz'])
         while wi<word_limit:
             host_time=wi/h2d_hz
             action_time=actions[ai][0] if ai<len(actions) else math.inf
             now=min(host_time,action_time)
             # Clocked consumers act before same-time new observations/frames.
             if split_time and now>playback.time:
                 middle=(playback.time+now)/2
                 returned.advance(middle);playback.advance(middle)
             returned.advance(now);playback.advance(now);pad.advance(now)
             if playback.fault:break
             for when,(kind,value,count) in returned.observed[seen:]:
                 if kind=='data':
                     bits=[(value>>i)&1 for i in range(count)]
                     if fpga_ingress is not None:
                         ingress_completions=[end for end in ingress_completions if end>when+1e-18]
                         capacity=fpga_ingress.get('capacity_records')
                         if capacity is not None and len(ingress_completions)>=capacity:
                             ingress_overflow=True
                             packet_parser.fault='FPGA ingress record capacity exceeded'
                         if ingress_overflow:continue
                     if packet_parser is not None:packet_parser.feed(bits)
                     else:host_bits.extend(bits)
                     if fpga_ingress is not None:
                         clock=fpga_ingress['clock_hz'];width=fpga_ingress['bits_per_cycle']
                         # Start on the next available local clock edge. A record
                         # occupies whole cycles; partial final words cost a cycle.
                         processing_phase=fpga_ingress.get('phase_cycles',0.)
                         start_cycle=math.ceil(max(ingress_visible(when),ingress_done)*clock-processing_phase-1e-9)
                         ingress_done=(start_cycle+processing_phase+math.ceil(count/width))/clock
                         ingress_peak_work_s=max(ingress_peak_work_s,ingress_done-when)
                         ingress_bits+=count
                         ingress_completions.append(ingress_done)
                         ingress_peak_records=max(ingress_peak_records,len(ingress_completions))
                 else:
                     assert value==7 and decision is None
                     # FPGA fixture uses only delivered records, never source bits.
                     if usb_data_packet:
                         try:
                             pid,decoded=packet_parser.finish()
                             if pid!=0xc3:raise ValueError('Unexpected transaction PID')
                         except ValueError as error:
                             packet_rejection=dict(reason=str(error),observed_at_s=when,decision_at_s=processing_ready(when,ingress_done))
                             rejections.append(packet_rejection);host_bits=[];packet_parser=USBStreamingPacket()
                             ingress_overflow=False
                             continue
                         host_bits=[];packet_rejection=None
                         response_payload=b'';response_levels=usb_hs_packet(0xd2)
                     else:
                         decoded=usb_decode(host_bits);response_payload=[1-bit for bit in decoded]
                         response_levels=usb_nrzi(response_payload)
                     for offset in range(0,len(response_levels),10):
                         bits=response_levels[offset:offset+10]
                         response_records.append(('data',sum(bit<<i for i,bit in enumerate(bits)),len(bits),when))
                     response_records.append(('event',7,0,when))
                     host_notice=when;fpga_ready=processing_ready(when,ingress_done)
                     decision=fpga_ready
                     if command_sync_cycles:
                         # The frame builder consumes one eight-word block per
                         # edge. Synchronize command publication into this domain;
                         # stable prepared response data accompanies the control.
                         block_hz=h2d_hz/8
                         decision=(math.ceil(fpga_ready*block_hz-1e-9)+command_sync_cycles)/block_hz
             seen=len(returned.observed)
             if abs(now-action_time)<1e-18:
                 _,kind,value=actions[ai];ai+=1
                 if kind=='retry':
                     assert len(rejections)==1 and packet_rejection is not None
                     assert now>packet_rejection['decision_at_s'] and playback.first_drive is None
                     assert not published and not response_records and not playback.writes and pad.local=='Z'
                     retry_state=dict(time_s=now,host_words=wi,host_sequence=sequence,
                         return_blocks=returned.reads,no_response_before_retry=True)
                 elif kind=='drive':pad.drive(peer='J' if value else 'K')
                 elif kind=='release':pad.drive()
                 else:
                     v=pad.observe();was_active=observer.in_burst
                     observer.observe(not v['squelch'],int(v['j']),now)
                     if was_active and not observer.in_burst:detected=now
             if abs(now-host_time)<1e-18:
                 if reference_pacer is not None and wi%2==0:
                     # One increment per rising D2H edge, not both DDR words.
                     reference_pacer.tick((returned.word_index//2)%65536)
                 if wi%8==0:
                     if prepared is not None:emitted=prepared
                     selected=[]
                     if decision is not None and now>decision:
                         # FPGA credit accrual uses its own clock, not ideal chip time.
                         if reference_pacer is None and token_time is not None:
                             tokens=min(60.,tokens+(now-token_time)*480e6*(h2d_hz/hz))
                         token_time=now
                         candidate=response_records[:3]
                         cost=sum(r[2] for r in candidate if r[0]=='data')
                         if (reference_pacer.take(cost) if reference_pacer is not None else (not host_pacing or cost<=tokens+1e-9)):
                             selected=candidate;response_records=response_records[len(candidate):]
                             if response_records and response_records[0][0]=='event':selected.append(response_records.pop(0))
                             if host_pacing and reference_pacer is None:tokens-=cost
                             published=published or bool(selected)
                     prepared=encode_records(selected,sequence);sequence=(sequence+1)%64
                 playback.feed(emitted[wi%8],now);wi+=1
             if playback.fault:break
             if playback.player.completed and now>playback.observed[-1][0]+3*ui:break
         if playback.fault:
             rows.append(dict(host_word_hz=hz,h2d_word_hz=h2d_hz,role=role,clock_phase=phase,playback_clock_phase=read_phase,request_bits=request_length,
                 delivered=False,fault=playback.fault,pad_released=pad.local=='Z'))
             assert pad.local=='Z'
             continue
         if packet_rejection is not None:
             assert now>release+400e-9 and now>packet_rejection['decision_at_s']
             assert not published and not response_records and playback.first_drive is None
             assert not playback.writes and not playback.player.emitted and pad.local=='Z'
             rows.append(dict(host_word_hz=hz,h2d_word_hz=h2d_hz,role=role,
                 clock_phase=phase,playback_clock_phase=read_phase,request_bits=request_length,
                 delivered=False,fault=None,packet_rejection=packet_rejection,
                 no_response=True,pad_released=True,observed_until_s=now,
                 ingress_peak_records=ingress_peak_records,
                 request_release_s=release))
             continue
         if retry_after_s is not None:assert retry_state is not None and len(rejections)==1
         assert published and playback.player.completed==1
         if usb_data_packet:
             assert decoded==request_bytes
             assert usb_hs_decode_packet([value for _,value in playback.observed])==(0xd2,b'')
         else:
             assert response_payload==[1-bit for bit in request]
             assert usb_decode([value for _,value in playback.observed])==response_payload
         assert pad.observe()['squelch'] and playback.writes==playback.reads
         latency=playback.first_drive-release
         rows.append(dict(host_word_hz=hz,h2d_word_hz=h2d_hz,role=role,clock_phase=phase,playback_clock_phase=read_phase,request_bits=request_length,delivered=True,fault=None,
             retry_state=retry_state,packet_rejections=rejections,observed_boundary_s=detected,host_notice_s=host_notice,fpga_ready_s=fpga_ready,command_ready_s=decision,
             fpga_ingress=dict(configuration=fpga_ingress,processed_bits=ingress_bits,peak_records=ingress_peak_records,peak_pending_work_s=ingress_peak_work_s,tail_work_s=max(0.,ingress_done-host_notice)),
             response_drive_s=playback.first_drive,response_latency_s=latency,
             latency_components_s=dict(pad_boundary_detection=detected-release,
                 return_transport=host_notice-detected,fpga_decision=fpga_ready-host_notice,
                 command_crossing=decision-fpga_ready,
                 response_transport_and_launch=playback.first_drive-decision),
             minimum_gap_s=8/480e6,budget_s=400e-9,meets_budget=8/480e6<=latency<=400e-9,
             ordered_response=True,h2d_blocks=playback.reads,d2h_blocks=returned.reads,
             d2h_high_water=returned.high_water,d2h_stalls=returned.stalls,playback_peak_bits=playback.playback_peak_bits,playback_capacity_bits=playback_capacity_bits))
    malformed=[]
    for corrupt_slot,mask in ((0,1),(7,8)):
        pad=SharedWiredPad();pad.configure('usb','device','hs',attached=True)
        tx=TimedRecordPlayback(pad)
        frame=encode_records([('data',1,10,0.),('data',1,10,0.),
                              ('data',1,3,0.),('event',7,0,0.)],0)
        frame[corrupt_slot]^=mask
        try:
            for i,word in enumerate(frame):tx.feed(word,i/250e6)
        except ValueError:pass
        else:raise AssertionError('Malformed response frame accepted')
        tx.advance(1e-6)
        assert tx.fault and tx.first_drive is None and not tx.writes and pad.local=='Z'
        malformed.append(dict(corrupt_slot=corrupt_slot,fault=tx.fault,no_pad_drive=True))
    return dict(cases=rows,reference_pacing=reference_pacing,host_clocked=host_clocked,command_sync_cycles=command_sync_cycles,fpga_ingress=requested_ingress,fpga_processing_s=(None if requested_ingress is not None and "decision_cycles" in requested_ingress else fpga_processing_s),usb_data_packet=usb_data_packet,packet_fault=packet_fault,retry_after_s=retry_after_s,h2d_clock_ppm=h2d_clock_ppm,host_pacing=host_pacing,coalesce_return=coalesce_return,malformed_frames=malformed,packet_scope=('DATA0 with CRC16 to ACK, full 32-bit SYNC and 8-bit unstuffed EOP, external FPGA parser; prior token/endpoint acceptance assumed, no transaction state or hub dribble' if usb_data_packet else 'Generic burst only'),scope=('Reference pacing uses observed D2H rising edges through ideal two-stage 16-bit counter visibility with sticky watchdog/discontinuity faults, assuming a fixed serializer/D2H clock ratio; no physical CDC or bridge-wide stop/flush recovery proof. ' if reference_pacing else '')+'Optional external FPGA token bucket: 60 raw bits at nominal 480 Mb/s scaled by the FPGA host-clock offset, no instantaneous chip-occupancy knowledge; nonzero sustained rate error eventually overflows or underruns finite storage. Clock tracking/service envelope unqualified. Connected finite generic burst request/reply, observed pad activity and both staged record transports. FPGA derives reply only from delivered records. Warmed clocks, prescribed sampling/serializer, declared bounded FPGA work, fixed pad model and selected phases. Packet framing is optional and described separately; no CDR, autonomous clock/load envelope or full lifecycle qualification.')



def usb_ingress_work_screen(*,processing_phases=(0.,),service_widths=(8,16),synchronizer_cycles=0,command_sync_cycles=0):
    """Finite external-FPGA workload screen; no physical timing-closure claim."""
    if not processing_phases or not service_widths:raise ValueError('Nonempty workload sweep required')
    rows=[]
    for processing_phase in processing_phases:
      for width in service_widths:
        for ppm in (-100.,100.):
            result=usb_observed_response(request_lengths=(8,64,512),
                usb_data_packet=True,host_pacing=True,coalesce_return=True,
                clock_phases=tuple((a,b) for a in (0.,.37,.99) for b in (0.,.37,.99)),
                h2d_clock_ppm=ppm,command_sync_cycles=command_sync_cycles,
                fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=width,
                                 capacity_records=8,phase_cycles=processing_phase,synchronizer_cycles=synchronizer_cycles))
            rows.extend(dict(row,bits_per_cycle=width,h2d_clock_ppm=ppm,
                             processing_phase=processing_phase) for row in result['cases'])
    summary=[]
    for processing_phase in processing_phases:
      for width in service_widths:
        for hz in (250e6,312.5e6):
            cases=[row for row in rows if row['bits_per_cycle']==width and row['host_word_hz']==hz and row['processing_phase']==processing_phase]
            summary.append(dict(processing_phase=processing_phase,bits_per_cycle=width,host_word_hz=hz,cases=len(cases),
                failures=sum(not row.get('meets_budget',False) for row in cases),
                rejected=sum(not row['delivered'] for row in cases),
                worst_latency_s=max((row['response_latency_s'] for row in cases if row['delivered']),default=None),
                peak_records=max(row['fpga_ingress']['peak_records'] if row['delivered'] else row['ingress_peak_records'] for row in cases)))
    return dict(summary=summary,cases=rows,synchronizer_cycles=synchronizer_cycles,
        scope='Finite 1/8/64-byte DATA0-to-ACK workloads, both roles, nine transport phase pairs and +/-100 ppm H2D. Independent processing clock phases, assumed parallel service with eight-record capacity and incremental parser; no FPGA timing closure, transaction acceptance, CDR or all-phase bound.')


def raw_record_playback_controls():
    """Generic raw-record decoder to physical pad, without response transport."""
    from bit_event_stream import RawBurstPlayback
    from bit_event_codec import encode_records,StreamingRecordReceiver
    rows=[]
    for role in ('host','device'):
        pad=SharedWiredPad();pad.configure('usb',role,'hs',attached=True)
        playback=RawBurstPlayback();receiver=StreamingRecordReceiver();seq=0
        for length in (1,10,23,61):
            payload=np.random.default_rng(710+length).integers(0,2,length).tolist()
            levels=usb_nrzi(payload);records=[]
            for start in range(0,len(levels),10):
                bits=levels[start:start+10]
                records.append(('data',sum(bit<<i for i,bit in enumerate(bits)),len(bits),0.))
            records.append(('event',7,0,0.))
            # Existing raw-record frames, including a final partial word/event.
            while records:
                selected=records[:3];records=records[3:]
                if records and records[0][0]=='event':selected.append(records.pop(0))
                frame=encode_records(selected,seq);seq=(seq+1)%64
                decoded=[]
                for word in frame:decoded.extend(receiver.feed(word))
                playback.enqueue(decoded)
            observed=[]
            for _ in levels:
                value=playback.tick();assert value is not None
                pad.drive(local='J' if value else 'K')
                pad.advance(pad.time+.5/480e6)
                assert not pad.observe()['squelch'];observed.append(int(pad.observe()['j']))
                pad.advance(pad.time+.5/480e6)
            assert playback.tick() is None
            pad.drive();pad.advance(pad.time+2/480e6)
            assert pad.observe()['squelch'] and usb_decode(observed)==payload
        assert playback.completed==4 and not playback.bits and not playback.queue
        rows.append(dict(role=role,completed_bursts=playback.completed,emitted_bits=playback.emitted))
    # Underrun cannot repeat the last level or resume on stale queued records.
    player=RawBurstPlayback();player.enqueue([('data',1,1)])
    assert player.tick()==1
    try:player.tick()
    except ValueError as error:assert str(error)=='Playback underrun'
    else:raise AssertionError('Missing boundary accepted')
    assert player.fault and player.tick() is None
    player=RawBurstPlayback(capacity_bits=10);player.enqueue([('data',1,10)])
    before=list(player.queue)
    try:player.enqueue([('data',1,1),('event',7,0)])
    except ValueError as error:assert str(error)=='Playback overflow'
    else:raise AssertionError('Playback overflow accepted')
    assert list(player.queue)==before and player.tick() is None
    return dict(cases=rows,underrun_releases=True,overflow_atomic=True,
        scope='Candidate generic raw-record TX consumer with bounded existing-queue-sized storage. Preloaded framed samples to persistent pad, prescribed serializer clock. No timed H2D/control path, response deadline, USB EOP or compliance proof. Boundary selects generic release, not protocol recognition.')


def usb_observed_boundaries():
    """Persistent pad to sampled activity records; prescribed sample clock."""
    from bit_event_stream import BitEventStream,SampledActivityBoundary
    from bit_event_codec import snapshot_records,StreamingRecordReceiver
    rows=[]
    for role in ('host','device'):
        pad=SharedWiredPad();pad.configure('usb',role,'hs',attached=True)
        stream=BitEventStream(capacity=16);observer=SampledActivityBoundary(stream)
        transport=TimedRecordReturn(stream,source_phase=.37)
        expected=[];delays=[];boundary_times=[]
        ui=1/480e6
        def sample(time):
            transport.advance(time)
            pad.advance(time);v=pad.observe()
            was_active=observer.in_burst
            observer.observe(not v['squelch'],int(v['j']),time)
            if was_active and not observer.in_burst:boundary_times.append(time)
        for length in (7,23,61):
            bits=np.random.default_rng(600+length).integers(0,2,length).tolist()
            levels=usb_nrzi(bits);captured=[]
            # Idle samples do not invent repeated boundaries.
            for _ in range(3):sample(pad.time+ui)
            for level in levels:
                start=pad.time;pad.drive(peer='J' if level else 'K')
                sample(start+.5*ui);captured.append(int(pad.observe()['j']))
                pad.advance(start+ui)
            assert usb_decode(captured)==bits
            pad.drive();release=pad.time
            for _ in range(5):sample(pad.time+ui)
            assert len(boundary_times)==len(delays)+1
            delays.append(boundary_times[-1]-release)
            expected.extend(('bit',level) for level in levels);expected.append(('event',7))
            # Idle clocks drain crossing/preparation without resetting pad/FIFO.
            sample(pad.time+300e-9)
        actual=[]
        for _,(kind,value,count) in transport.observed:
            if kind=='data':actual.extend(('bit',(value>>n)&1) for n in range(count))
            else:actual.append(('event',value))
        assert actual==expected and len(delays)==3
        assert all(abs(delay-2*ui)<1e-15 for delay in delays)
        host_boundaries=[time for time,r in transport.observed if r[0]=='event']
        host_delays=[end-start for start,end in zip(boundary_times,host_boundaries)]
        assert len(host_boundaries)==3 and all(delay>0 for delay in host_delays)
        assert transport.writes==transport.reads and not stream.records and not stream.valid_bits
        rows.append(dict(role=role,burst_lengths=[7,23,61],boundary_delays_s=delays,
            host_boundary_delays_s=host_delays,cdc_blocks=transport.reads,
            cdc_high_water=transport.high_water,
            ordered_records=True,persistent_pad_and_receiver=True))
    # A comparator dropout must not silently splice two pieces of a burst.
    stream=BitEventStream();observer=SampledActivityBoundary(stream)
    observer.observe(True,1,0.);observer.observe(False,0,1e-9)
    try:observer.observe(True,0,2e-9)
    except ValueError:pass
    else:raise AssertionError('Unqualified dropout accepted')
    assert observer.fault and stream.fault
    try:stream.pop()
    except ValueError:pass
    else:raise AssertionError('Faulted samples delivered')
    lone=BitEventStream();lone.bit(1,0.)
    for _ in range(9):lone.bit(0,0.)
    grouped=TimedRecordReturn(lone,coalesce=True)
    grouped.advance(0.);assert grouped.writes==0
    grouped.advance(25e-9);assert grouped.writes==1
    lone.event(7,26e-9);grouped.advance(50e-9)
    assert grouped.writes==2  # Boundary never waits for a second data record.
    grouped.advance(300e-9)
    assert [r for _,r in grouped.observed]==[('data',1,10),('event',7,0)]
    sustained=[]
    for rate in (480e6,2e9):
        stream=BitEventStream(16);transport=TimedRecordReturn(stream,source_phase=.37)
        fault=None
        try:
            for i in range(4096):
                time=(i+1)/rate;transport.advance(time);stream.bit(i%2,time)
            stream.event(7,time);transport.advance(time+2e-6)
        except ValueError as error:
            if str(error)!='Bit/event stream overflow':raise
            fault=str(error)
        if rate==480e6:
            assert fault is None
            actual=[(value>>n)&1 for _,(kind,value,count) in transport.observed
                    if kind=='data' for n in range(count)]
            assert actual==[i%2 for i in range(4096)]
            assert [r for _,r in transport.observed if r[0]=='event']==[('event',7,0)]
            assert transport.writes==transport.reads and not stream.records
        else:assert fault and stream.fault
        sustained.append(dict(input_bit_hz=rate,delivered=fault is None,fault=fault,
            cdc_blocks=transport.reads,source_stalls=transport.stalls,
            cdc_high_water=transport.high_water))
    return dict(cases=rows,sustained_record_controls=sustained,short_dropout_fault=True,
        coalescing_single_word_bound=True,boundary_bypasses_coalescing=True,
        scope='Finite pad voltage to generic activity boundary and actual raw-record codec, persistent across three bursts. Prescribed mid-bit sampling, ideal comparator, no CDR or USB packet/EOP recognition. Observed records traverse persistent block CDC, continuous idle/data host frames and one-frame preparation. Source encoding is functional, clocks warmed idle; response application remains unconnected.')


def usb_pad_lifecycle():
    """Electrical role/drive sequencing using the existing finite shared pad.

    Hold durations are model probes, not a USB attach/reset/chirp compliance trace.
    """
    staged_bounds=[usb_framed_turnaround(word_hz=rate,h2d_commit_words=16,h2d_cdc_hz=40e6)
                   for rate in (250e6,312.5e6)]
    assert all(not row['meets_bound'] for row in staged_bounds)
    payload=[1]*12+np.random.default_rng(119).integers(0,2,52).tolist()
    levels=usb_nrzi(payload);results=[]
    for role in ('host','device'):
        pad=SharedWiredPad();pad.configure('usb',role,'fs',attached=True)
        pad.advance(2e-6);idle=pad.observe()
        assert idle['j'] and not idle['se0']
        pad.drive(local='SE0' if role=='host' else 'Z',peer='SE0' if role=='device' else 'Z')
        pad.advance(pad.time+2e-6);assert pad.observe()['se0']
        pad.drive();pad.configure('usb',role,'hs',attached=True)
        for direction in ('local','peer'):
            captured=[]
            for level in levels:
                state='J' if level else 'K'
                pad.drive(**{direction:state})
                pad.advance(pad.time+.5/480e6)
                observation=pad.observe()
                assert not observation['squelch']
                captured.append(int(observation['j']))
                pad.advance(pad.time+.5/480e6)
            assert usb_decode(captured)==payload
            pad.drive();pad.advance(pad.time+20e-9)
            assert pad.observe()['squelch']
        before=(pad.local,pad.peer)
        try:pad.drive('J','K')
        except ValueError:pass
        else:raise AssertionError('Bus contention accepted')
        assert (pad.local,pad.peer)==before
        results.append(dict(role=role,payload_bits=len(payload),stuffed_line_bits=len(levels),
            local_and_peer_decode=True,released_squelch=True,turnaround=usb_framed_turnaround(),
            staged_h2d_turnaround_bounds=staged_bounds))
    assert all(row['turnaround']['meets_bound'] for row in results)
    assert not usb_framed_turnaround(frame_words=64)['meets_bound']
    return results


def behavioral_coverage(contract,scenarios,configurations):
    """Coverage is evidence classification, never inferred from runner success."""
    rows=[]
    for profile in contract['protocol_profiles']:
        nominal=[row for row in scenarios if row['target']==profile['id'] and row['uncertainty_case']=='candidate']
        assert nominal
        rf=profile['engine']=='rf'
        video=profile['id'] in ('hdmi_tmds','dvi_single_link')
        covered=['finite directional transport','average supply/current budget']
        missing=['physical parameter evidence','full protocol compliance','complete target-path payload-through-host identity']
        if rf:
            covered+=['synthetic RF modulation/conversion','training timing/gain','carrier and impairment diagnostic comparisons','shared persistent RF/filter and host sample-state tests']
            missing+=['standard packet acquisition','sensitivity/spectral-mask envelope','unified live-path acquisition/quality for this target','TX/RX turnaround']
        elif video:
            covered+=['separate three-lane forwarded PLL/pad acquisition screen']
            missing+=['connected multi-chip payload alignment','clock/data physical skew envelope']
        else:
            covered+=['static eye/jitter budget']
            missing+=['protocol electrical event sequence']
            if profile['id']!='usb2':
                covered+=['shared incremental channel/slicer/CDR-to-host fixtures at target rates']
                missing+=['integrated cold acquisition and protocol-specific encoded payload']
            else:
                covered+=['host/device pad lifecycle and stuffed NRZI voltage probes']
                missing+=['connected burst CDR and host-delivered packet payload']
        if profile['id']=='usb2':missing+=['host/device reset, chirp, attach and turnaround composition']
        rows.append(dict(target=profile['id'],covered=covered,missing=missing,
            external_stack_implementation_required_on_chip=False,
            physical_qualification_required_before_layout_acceptance=True,
            missing_items_are_not_all_same_stage=True,
            baseline_candidate_pass=all(row['status']=='conditional_candidate' for row in nominal),
            full_behavioral_closure=False))
    rows.append(dict(target='hd_sdi',covered=['numeric rate transport','CDR/holdover and false-lock diagnostics','incremental channel/CDR-to-host random payload at both rates'],
        missing=['encoded pathological patterns','coax interface/channel','integrated acquisition and encoded payload'],full_behavioral_closure=False))
    return rows


def run():
    started = time.monotonic()
    contract = json.loads((P/'spec/contract.json').read_text())
    assert len(contract['pins']) <= contract['limits']['total_terminals']
    assert sum(contract['area_um2'].values()) <= contract['limits']['core_area_um2']
    scenarios = []
    for label, assumptions in (
        ('candidate', Assumptions()),
        ('adverse_quality', Assumptions(converter_enob=6., relative_lo_phase_rms_rad=.12,
            wire_random_jitter_s=30e-12)),
        ('slow_host', Assumptions(host_clock_scale=.7)),
        ('heavy_host_load', Assumptions(host_output_cap_f=100e-12))):
        for profile in contract['protocol_profiles']:
            engine = profile['engine']
            for rate in profile.get('line_rates_bps', [profile.get('line_rate_bps')]):
                mode = 0 if engine == 'rf' or rate <= 1.25e9 else 1
                resource = dict(engine=engine, line_rate_bps=rate,
                    frame_words=8 if profile['host_service']=='short_framed' else 64,
                    pad_path='bidirectional' if profile['host_service']=='short_framed' else 'serial')
                chip = BehavioralChip(assumptions)
                chip.configure(encode_resource_word(**resource))
                chip.start(); chip.advance(assumptions.startup_s)
                wave=fixture(profile['id']) if engine=='rf' else None
                window_frames=max(128,math.ceil((wave.duration+544/40e6+(54.4e-6 if wave.kind=='he20' else 0))*(250e6 if mode==0 else 312.5e6)*assumptions.host_clock_scale/resource['frame_words'])) if wave is not None else 128
                directions=('rx','tx') if engine=='rf' or profile.get('duplex')=='full' else ('rx',)
                flow = chip.transfer(frames=window_frames,directions=directions,mode=mode, source_hz=40e6 if engine=='rf' else rate/10,
                    sample_bits=24 if engine=='rf' else 10, epoch=chip.epoch)
                quality = quality_budget(chip.resources, assumptions,
                    bandwidth_hz=profile.get('channel_bandwidth_max_hz'), carrier_hz=profile.get('carrier_max_hz'))
                power=power_budget(chip.resources,assumptions,flow,contract,mode=mode,
                    dc_sink=profile['id'] in ('dvi_single_link','hdmi_tmds'))
                waveform=waveform_screen(wave,assumptions,power) if wave is not None else None
                if waveform is not None and flow['fault'] is None:
                    assert flow['simulated_s']>=wave.duration+544/40e6+(54.4e-6 if wave.kind=='he20' else 0)
                scenarios.append(dict(target=profile['id'], uncertainty_case=label, assumptions=asdict(assumptions),
                    configuration=chip.resources, host_mode=mode, flow=flow, quality=quality,power=power,waveform=waveform,
                    status='conditional_candidate' if flow['fault'] is None and quality['conditional_screen_pass'] and power['conditional_screen_pass'] and (waveform is None or waveform['conditional_screen_pass']) else 'fails_assumed_envelope',
                    unclosed_gates=profile['required_gates'], chip_instances=profile.get('chip_instances',1)))
    assert all(r['power']['conditional_screen_pass'] for r in scenarios if r['uncertainty_case']=='candidate')
    assert all(not r['power']['conditional_screen_pass'] for r in scenarios if r['uncertainty_case']=='heavy_host_load')
    assert all(r['power']['average_current_a']['RF']==0 for r in scenarios if r['configuration']['engine']=='wire')
    signal=np.array([1+1j,0j,-.2j,.3,0j])
    f=EnvelopeFilter(40e6,9.157407e6);g=EnvelopeFilter(40e6,9.157407e6)
    assert np.allclose(f.process(signal),np.r_[g.process(signal[:2]),g.process(signal[2:])],rtol=0,atol=1e-15)
    expected_step=1-math.exp(-2*math.pi*9.157407e6/40e6)
    assert abs(EnvelopeFilter(40e6,9.157407e6).process([1])[0]-expected_step)<1e-15
    rf_row=next(r for r in scenarios if r['target']=='wifi_he20' and r['uncertainty_case']=='candidate')
    test_wave=fixture('wifi_he20')
    repeat=waveform_screen(test_wave,Assumptions(),rf_row['power'])
    assert repeat==rf_row['waveform']
    overdrive=waveform_screen(test_wave,replace(Assumptions(),converter_backoff_db=0.),rf_row['power'])
    assert overdrive['dac_clipped_samples']>0
    reduced_power={**rf_row['power'],'estimated_rail_v':{**rf_row['power']['estimated_rail_v'],'RF':.8*3.3}}
    sag=waveform_screen(test_wave,Assumptions(),reduced_power)
    assert sag['rf_rail_gain']<repeat['rf_rail_gain'] and sag['raw_received_rms_v']<repeat['raw_received_rms_v']
    # Gain/equalization can recover a moderate static sag; raw attenuation is checked above.
    # Lifecycle and service negative controls use the same model.
    c=BehavioralChip(Assumptions());c.configure(encode_resource_word(engine='rf'));c.start()
    def rejected(fn):
        try:fn()
        except ValueError:return
        raise AssertionError('Invalid lifecycle operation accepted')
    rejected(lambda:c.receive(mode=0,source_hz=40e6,sample_bits=24,epoch=0))
    rejected(lambda:c.configure(encode_resource_word(engine='wire',line_rate_bps=1.25e9)))
    c.advance(20e-6);old=c.epoch;c.lose_reference();c.configure(encode_resource_word(engine='wire',line_rate_bps=1.25e9));c.start();c.advance(40e-6)
    rejected(lambda:c.receive(mode=0,source_hz=125e6,sample_bits=10,epoch=old))
    paused=c.receive(mode=0,source_hz=125e6,sample_bits=10,host_pause_frames=16,epoch=c.epoch)
    assert paused['fault']=='overflow'
    def tx_case(prefill,pause=0):
        chip=BehavioralChip(Assumptions());chip.configure(encode_resource_word(engine='wire',line_rate_bps=1.25e9))
        chip.start();chip.advance(20e-6)
        return chip.transfer(mode=0,source_hz=125e6,sample_bits=10,directions=('tx',),
            epoch=chip.epoch,tx_prefill_bits=prefill,host_pause_frames=pause)
    assert tx_case(512)['fault'] is None
    assert tx_case(0)['fault']=='underflow'
    assert tx_case(512,16)['fault']=='underflow'
    half=BehavioralChip(Assumptions())
    half.configure(encode_resource_word(engine='wire',line_rate_bps=480e6,frame_words=8,pad_path='bidirectional'))
    half.start();half.advance(20e-6)
    rejected(lambda:half.transfer(mode=0,source_hz=48e6,sample_bits=10,epoch=half.epoch))
    def continuous_chip():
        chip=BehavioralChip(Assumptions(source_clock_scale=1.0001,h2d_clock_scale=1.0001,d2h_clock_scale=.9999))
        chip.configure(encode_resource_word(engine='rf'));chip.start();chip.advance(20e-6)
        return chip
    whole=continuous_chip();split=continuous_chip()
    args=dict(mode=0,source_hz=40e6,sample_bits=24,epoch=0)
    once=whole.transfer(frames=128,**args)
    split.transfer(frames=17,**args);split.transfer(frames=46,**args)
    chunked=split.transfer(frames=65,**args)
    assert once==chunked and whole.time==split.time and whole.stream==split.stream
    rejected(lambda:split.advance(split.time+1e-6))
    rejected(lambda:split.transfer(tx_prefill_bits=1024,**args))
    drift_cases=[]
    for tx_scale,rx_scale,direction,expected in ((.98,1.,('tx',),'underflow'),
            (1.02,1.,('tx',),'tx_overflow'),(1.,.8,('rx',),'overflow')):
        chip=BehavioralChip(Assumptions(h2d_clock_scale=tx_scale,d2h_clock_scale=rx_scale))
        chip.configure(encode_resource_word(engine='rf'));chip.start();chip.advance(20e-6)
        outcome=chip.transfer(mode=0,source_hz=40e6,sample_bits=24,frames=512,
            directions=direction,epoch=chip.epoch)
        assert outcome['fault']==expected,(tx_scale,rx_scale,outcome)
        drift_cases.append(dict(h2d_scale=tx_scale,d2h_scale=rx_scale,**outcome))
    feedback_cases=[]
    for scale in (.99,1.01):
        results=[]
        for enabled in (False,True):
            chip=BehavioralChip(Assumptions(h2d_clock_scale=scale))
            chip.configure(encode_resource_word(engine='rf'));chip.start();chip.advance(20e-6)
            results.append(chip.transfer(mode=0,source_hz=40e6,sample_bits=24,frames=1024,
                directions=('tx',),epoch=chip.epoch,feedback=enabled))
        assert results[0]['fault'] in ('underflow','tx_overflow')
        assert results[1]['fault'] is None,results[1]
        feedback_cases.append(dict(h2d_scale=scale,uncontrolled=results[0],controlled=results[1]))
    loss=BehavioralChip(Assumptions());loss.configure(encode_resource_word(engine='rf'));loss.start();loss.advance(20e-6)
    lost=loss.transfer(mode=0,source_hz=40e6,sample_bits=24,directions=('tx',),epoch=0,
        feedback=True,feedback_stop_after=4)
    assert lost['fault']=='stale_feedback'
    whole_feedback=continuous_chip();split_feedback=continuous_chip()
    feedback_args=dict(args,feedback=True)
    expected_feedback=whole_feedback.transfer(frames=128,**feedback_args)
    split_feedback.transfer(frames=31,**feedback_args)
    assert split_feedback.transfer(frames=97,**feedback_args)==expected_feedback
    assert split_feedback.stream==whole_feedback.stream
    limited=BehavioralChip(Assumptions(h2d_clock_scale=.98))
    limited.configure(encode_resource_word(engine='rf'));limited.start();limited.advance(20e-6)
    insufficient=limited.transfer(mode=0,source_hz=40e6,sample_bits=24,frames=1024,
        directions=('tx',),epoch=0,feedback=True)
    assert insufficient['h2d_capacity_bps']<insufficient['required_bps'] and insufficient['fault']=='underflow'
    discarded=split.lose_reference()
    assert discarded==dict(rx_bits=chunked['pending_bits'],tx_bits=chunked['tx']['pending_bits'])
    assert split.stream is None and split.epoch==1
    assert all(r['flow']['fault'] is None for r in scenarios if r['uncertainty_case']=='candidate')
    assert any(r['flow']['fault'] for r in scenarios if r['uncertainty_case']=='slow_host')
    assert any(not r['quality']['conditional_screen_pass'] for r in scenarios if r['uncertainty_case']=='adverse_quality')
    files=[Path(__file__),P/'spec/contract.json',P/'verification/stream_codec.py',P/'verification/bit_event_codec.py',P/'system_model/connected/bit_event_stream.py',P/'verification/block_receiver_model.py',P/'evidence/block-fifo-mapping.json',P/'verification/transport_model.py',Path(__file__).with_name('resource_configuration.py'),P/'system_model/connected/protocol_signals.py',P/'system_model/connected/lane_group.py',P/'system_model/connected/sampled_pll.py',P/'system_model/connected/reference_sample_clock.py',P/'system_model/connected/autonomous_pll.py',P/'system_model/connected/oscillator_noise.py',P/'system_model/connected/protocol_pad.py',P/'system_model/connected/shaped_fractional_pll.py',P/'system_model/connected/fractional_pulse_pll.py']
    known=np.repeat(np.exp(1j*np.random.default_rng(23).uniform(-math.pi,math.pi,128)),4)
    delayed=np.r_[np.zeros(2),known[:-2]]*(.7+.2j)
    trained=acquire_training(delayed,40e6,known)
    assert trained['acquired'] and abs(trained['delay_s']-3/40e6)<1e-15
    assert abs(trained['gain']-(.7+.2j))<1e-12
    long_delay=np.r_[np.zeros(12),known[:-12]]
    recovered_delay=acquire_training(long_delay,40e6,known,24)
    assert recovered_delay['acquired'] and abs(recovered_delay['delay_s']-13/40e6)<1e-15
    assert not acquire_training(long_delay,40e6,known,8)['acquired']
    for scale in (.5,2.):
        scaled=acquire_training(delayed*scale,40e6,known)
        assert scaled['acquired'] and scaled['delay_s']==trained['delay_s']
        assert abs(scaled['gain']-trained['gain']*scale)<1e-12
        assert abs(scaled['residual']-trained['residual'])<1e-12
    assert not acquire_training(np.zeros_like(known),40e6,known)['acquired']
    assert not acquire_training(delayed,40e6,known[::-1])['acquired']
    # Verify interpolated chirps independently of the analog pass/fail score.
    for bandwidth in (203125.,406250.,812500.,1625000.):
        symbols=np.arange(128)
        original=lora(symbols,bandwidth=bandwidth)
        dense=lora(symbols,bandwidth=bandwidth,oversample=8)
        assert dense.duration==original.duration
        assert np.max(abs(dense.samples[::8]-original.samples))<1e-10
        assert np.array_equal(decisions(dense),symbols)
        # Frequency stays inside the declared channel, excluding symbol joins.
        rows=dense.samples.reshape(128,-1)
        frequency=np.angle(rows[:,1:]*rows[:,:-1].conj())*dense.sample_hz/(2*math.pi)
        assert np.max(abs(frequency))<=bandwidth/2+1e-5
    # A trained observer must reject an erased channel, not invert it.
    training_wave=fixture('wifi_he20',seed=1907)
    eq=TrainedBlockEqualizer(256,training_wave.metadata['cp'],np.asarray(training_wave.metadata['data'])%256)
    try:eq.train(training_wave.samples,np.zeros_like(training_wave.samples))
    except ValueError:pass
    else:raise AssertionError('Erased training channel accepted')
    assert eq.response is None
    assert rf_row['waveform']['equalized']['evm_rms']<.10
    adverse=next(r for r in scenarios if r['target']=='wifi_he20' and r['uncertainty_case']=='adverse_quality')
    assert adverse['waveform']['equalized']['evm_rms']>.10
    expanded=configuration_sweep(contract)
    cdr=[transition_cdr_screen(rate,initial_ppm=ppm,gap_frequency_step_ppm=step)
         for rate in (1.485e9,1.485e9/1.001) for ppm in (-100.,100.) for step in (0.,100.)]
    assert all(row['acquired'] for row in cdr)
    assert all(row['payload_identity_preserved'] for row in cdr if not row['gap_frequency_step_ppm'])
    assert all(row['payload_errors']>0 for row in cdr if row['gap_frequency_step_ppm'])
    assert all(not row['timing_survives_gap'] for row in cdr if row['gap_frequency_step_ppm'])
    holdover=[clock_holdover_screen(rate,frequency_error_ppm=ppm,gap_bits=gap)
              for rate in (1.485e9,1.485e9/1.001)
              for ppm in (-100.,100.) for gap in (10,100,1000,10000)]
    assert all(row['holdover_within_assumed_eye'] for row in holdover if row['gap_bits']<=1000)
    assert all(not row['holdover_within_assumed_eye'] for row in holdover if row['gap_bits']==10000)
    assert clock_holdover_screen(1.485e9,frequency_error_ppm=0.,gap_bits=10000)['drift_ui']==0
    timing_failure=forwarded_pll_acquisition(148.5e6,noise_rms_hz=20e6)
    assert not timing_failure['group_timing_ready']
    distortion=rf_distortion_diagnostics()
    offsets=carrier_offset_diagnostics(contract)
    for row in offsets:
        if 'configuration' in row:
            recovery=row['recovered']['carrier_recovery']
            assert recovery['acquired'] and abs(recovery['estimate_hz']-row['offset_hz'])<100
            assert row['recovered']['symbol_errors']==0
    # Repetition alone cannot distinguish offsets separated by Fs/lag.
    t=np.arange(64)/5e6
    aliased,_=repeated_training_frequency(np.exp(2j*math.pi*100e3*t),32,5e6)
    assert abs(aliased-(-56250.))<1e-8
    assert all(not row['quality']['timing_recovery']['acquired'] for row in offsets if row['offset_hz'] and 'quality' in row)
    assert all(row['quality']['symbol_errors']>0 for row in offsets
               if 'quality' in row and row['offset_hz'] and row['fixture'] in ('wifi_he20','ieee802154_24','lora_24'))
    phase=np.array([-.7,.2,1.1])
    data=np.array([[1,-1],[1,1],[-1,1]],complex)
    corrected,_=pilot_phase_correct(data*np.exp(1j*phase[:,None]),np.ones((3,8))*np.exp(1j*phase[:,None]))
    assert np.allclose(corrected,data,atol=1e-14)
    try:pilot_phase_correct(data,np.zeros((3,8)))
    except ValueError:pass
    else:raise AssertionError('Missing pilots accepted')
    bursts=burst_robustness(contract) if '--burst-stress' in sys.argv else None
    rng=np.random.default_rng(270)
    signal=rng.normal(size=1024)+1j*rng.normal(size=1024)
    for order in (1,5):
        whole_filter=MultipoleEnvelope(10e6,1.25e6,order)
        split_filter=MultipoleEnvelope(10e6,1.25e6,order)
        expected=whole_filter.process(signal)
        actual=np.concatenate([split_filter.process(chunk) for chunk in np.split(signal,[1,31,128,129,777])])
        assert np.allclose(actual,expected,rtol=0,atol=1e-13)
        assert np.allclose(split_filter.state,whole_filter.state,rtol=0,atol=1e-13)
        before=split_filter.state.copy()
        assert len(split_filter.process([]))==0 and np.array_equal(before,split_filter.state)
        try:split_filter.process([float('nan')])
        except ValueError:pass
        else:raise AssertionError('Nonfinite filter input accepted')
        assert np.array_equal(before,split_filter.state)
        split_filter.reset()
        assert np.array_equal(split_filter.state,np.zeros(order))
        assert np.allclose(split_filter.process(signal),expected,rtol=0,atol=1e-13)
    settings=dict(sample_hz=10e6,tx_cutoff_hz=5e6,rx_cutoff_hz=1.25e6,rx_filter_order=5)
    whole_stream=SampledRFStream(settings,offset_hz=48000.)
    split_stream=SampledRFStream(settings,offset_hz=48000.)
    expected_stream=whole_stream.process(signal*.1)
    actual_stream=np.concatenate([split_stream.process(chunk) for chunk in np.split(signal*.1,[1,31,128,129,777])])
    assert np.array_equal(actual_stream,expected_stream)
    assert split_stream.index==whole_stream.index and split_stream.previous_tx==whole_stream.previous_tx
    assert split_stream.rng.bit_generator.state==whole_stream.rng.bit_generator.state
    assert split_stream.dac_clips==whole_stream.dac_clips and split_stream.adc_clips==whole_stream.adc_clips
    split_stream.reset()
    assert np.array_equal(split_stream.process(signal*.1),expected_stream)
    # Actual quantized I/Q values cross the same scheduled ten-bit host slots.
    packed=[int(round(z.real*2048))%4096 | ((int(round(z.imag*2048))%4096)<<12) for z in expected_stream]
    source=lambda index:packed[index]
    def receiver():
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='rf',rf=settings);chip.start();chip.advance(chip.ready_at)
        return chip
    whole_rx=receiver();split_rx=receiver()
    args=dict(mode=0,source_hz=10e6,sample_bits=24,epoch=0,rx_source=source)
    result=whole_rx.receive(frames=64,**args)
    split_rx.receive(frames=17,**args);split_rx.receive(frames=47,**args)
    assert whole_rx.stream['rx_words']==split_rx.stream['rx_words']
    assert whole_rx.stream['rx_buffer']==split_rx.stream['rx_buffer']
    words=whole_rx.stream['rx_words']
    returned_value=sum(word<<(10*i) for i,word in enumerate(words))
    expected_value=sum(value<<(24*i) for i,value in enumerate(packed[:result['produced_bits']//24]))
    assert returned_value | (whole_rx.stream['rx_buffer']<<result['returned_bits'])==expected_value
    live=BehavioralChip(Assumptions())
    live.configure_numeric(engine='rf',rf=settings)
    live.attach_rf_stream(lambda index:signal[index]*.1,offset_hz=48000.)
    live.start();live.advance(live.ready_at)
    live_args={key:value for key,value in args.items() if key!='rx_source'}
    live.receive(frames=17,**live_args);live.receive(frames=47,**live_args)
    assert live.stream['rx_words']==words and live.stream['rx_buffer']==whole_rx.stream['rx_buffer']
    assert live.rf_stream.index==result['produced_bits']//24
    stale_source=live.rf_source;core=live.rf_stream
    before_stop=core.index;filter_state=core.rx.state.copy()
    live.stop()
    assert core.index==before_stop and np.array_equal(core.rx.state,filter_state)
    assert live.parked_rf is core and live.rf_stream is None and live.rf_source is None
    try:stale_source(0)
    except ValueError:pass
    else:raise AssertionError('Stopped converter callback remained usable')
    # Actual H2D word payload plus non-word-aligned prefill reconstructs DAC samples.
    tx_bits_value=sum(value<<(24*i) for i,value in enumerate(packed))
    tx_source=lambda index:(tx_bits_value>>(512+10*index))&1023
    tx_args=dict(mode=0,source_hz=10e6,sample_bits=24,epoch=0,directions=('tx',),
        tx_source=tx_source,tx_prefill_value=tx_bits_value&((1<<512)-1))
    tx_whole=receiver();tx_split=receiver()
    tx_result=tx_whole.transfer(frames=64,**tx_args)
    tx_split.transfer(frames=17,**tx_args);tx_split.transfer(frames=47,**tx_args)
    assert tx_whole.stream['tx_samples']==tx_split.stream['tx_samples']
    assert tx_whole.stream['tx_samples']==packed[:len(tx_whole.stream['tx_samples'])]
    assert tx_whole.stream['tx_buffer']==tx_split.stream['tx_buffer']
    def unpack_iq(value):
        i=value&4095;q=(value>>12)&4095
        return ((i if i<2048 else i-4096)+1j*(q if q<2048 else q-4096))/2048
    impairments=dict(blocker_v=.05,blocker_hz=3e6,saturation_v=1.,ripple_v=.02,ripple_hz=1e6,lo_supply_hz_per_v=1e6)
    def loopback():
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_rf_stream(lambda index:unpack_iq(chip.stream['tx_buffer']&((1<<24)-1)),offset_hz=48000.,**impairments)
        chip.start();chip.advance(chip.ready_at)
        return chip
    loop_whole=loopback();loop_split=loopback()
    loop_args=dict(tx_args,directions=('rx','tx'))
    loop_result=loop_whole.transfer(frames=64,**loop_args)
    loop_split.transfer(frames=17,**loop_args);loop_split.transfer(frames=47,**loop_args)
    assert loop_result['fault'] is None
    assert loop_whole.stream['rx_words']==loop_split.stream['rx_words']
    assert loop_whole.stream['rx_buffer']==loop_split.stream['rx_buffer']
    assert loop_whole.stream['tx_samples']==loop_split.stream['tx_samples']
    reference=SampledRFStream(settings,offset_hz=48000.,**impairments)
    adc=reference.process([unpack_iq(value) for value in loop_whole.stream['tx_samples']])
    adc_packed=[int(round(z.real*2048))%4096 | ((int(round(z.imag*2048))%4096)<<12) for z in adc]
    observed=sum(word<<(10*i) for i,word in enumerate(loop_whole.stream['rx_words']))
    observed|=loop_whole.stream['rx_buffer']<<loop_result['returned_bits']
    assert observed==sum(value<<(24*i) for i,value in enumerate(adc_packed))
    starved=loopback()
    fault=starved.transfer(frames=1,**dict(loop_args,tx_prefill_bits=0,tx_prefill_value=0))
    assert fault['fault']=='underflow' and starved.rf_stream.index==0
    for scale in (.9999,1.0001):
        drift_chip=BehavioralChip(Assumptions(source_clock_scale=scale))
        drift_chip.configure_numeric(engine='rf',rf=settings)
        drift_chip.attach_rf_stream(lambda index:signal[index]*.1,offset_hz=48000.)
        drift_chip.start();drift_chip.advance(drift_chip.ready_at)
        drift_flow=drift_chip.receive(frames=64,**live_args)
        count=drift_flow['produced_bits']//24
        assert drift_chip.rf_stream.actual_sample_hz==10e6*scale
        reference=SampledRFStream(settings,offset_hz=48000.,clock_scale=scale)
        expected=reference.process(signal[:count]*.1)
        expected_bits=sum((int(round(z.real*2048))%4096 | ((int(round(z.imag*2048))%4096)<<12))<<(24*i) for i,z in enumerate(expected))
        got=sum(word<<(10*i) for i,word in enumerate(drift_chip.stream['rx_words']))
        got|=drift_chip.stream['rx_buffer']<<drift_flow['returned_bits']
        assert got==expected_bits and drift_flow['fault'] is None
    # Alternate 8-bit I/Q mode uses actual 16-bit samples and mode-1 slots.
    eight_settings=dict(settings,sample_hz=20e6,converter_bits=8)
    eight=BehavioralChip(Assumptions())
    eight.configure_numeric(engine='rf',rf=eight_settings)
    eight.attach_rf_stream(lambda index:signal[index]*.1,offset_hz=48000.)
    eight.start();eight.advance(eight.ready_at)
    result8=eight.receive(mode=1,source_hz=20e6,sample_bits=16,frames=64,epoch=0)
    count8=result8['produced_bits']//16
    reference8=SampledRFStream(eight_settings,offset_hz=48000.).process(signal[:count8]*.1)
    expected8=sum((int(round(z.real*128))%256 | ((int(round(z.imag*128))%256)<<8))<<(16*i) for i,z in enumerate(reference8))
    actual8=sum(word<<(10*i) for i,word in enumerate(eight.stream['rx_words']))
    actual8|=eight.stream['rx_buffer']<<result8['returned_bits']
    assert actual8==expected8 and result8['fault'] is None
    probe=np.ones(2048,complex)
    assert np.allclose(multipole_envelope(probe,10e6,1e6,1),EnvelopeFilter(10e6,1e6).process(probe),atol=1e-12)
    assert abs(multipole_envelope(probe,10e6,1e6,5)[-1]-1)<1e-12
    bounded,gain=compress_envelope(np.array([0.,1e-6,1.,1e6]),1.)
    assert gain[0]==1. and abs(gain[2]-1/math.sqrt(2))<1e-15
    assert np.all(abs(bounded)<1.) and np.all(np.diff(bounded.real)>0)
    rotated,_=compress_envelope(np.array([1j]),1.)
    assert abs(rotated[0]-1j/math.sqrt(2))<1e-15
    wired_delivery=[row for rate in (1.25e9,1.485e9/1.001,1.485e9,1.5e9,1.62e9,2.5e9) for row in cdr_host_delivery(rate)]
    cold_delivery=cold_cdr_host_delivery()
    qualification=cdr_qualification_controls()
    alignment=observed_alignment_controls()
    aligned_delivery=aligned_host_delivery()
    raw_alignment=raw_host_alignment_controls()
    raw_reference_recovery=raw_host_alignment_controls(reference_gap=True)
    raw_clock_recovery=raw_host_alignment_controls(host_clock_gap=True)
    aligned_cancel=aligned_reference_cancellation()
    aligned_recovery=aligned_reference_recovery()
    wired_reference_presence=wired_reference_presence_controls()
    usb_lifecycle=usb_pad_lifecycle()
    connected_payload=connected_gfsk_payload(12)+connected_gfsk_payload(8)
    rf_tx_only=rf_transmit_without_rx()
    rf_recovery=retained_rf_recovery()
    reference_presence=reference_presence_controls()
    lo_controls=lo_clock_controls()
    lo_supply=lo_supply_controls()
    exclusive_transport=exclusive_transport_controls()
    timed_lifecycle=timed_rf_lifecycle_controls()
    converter_timing=converter_timing_controls()
    lo_integration=lo_integration_controls()
    host_activity=host_activity_controls()
    lo_reference_phase=lo_reference_phase_controls()
    lo_noise_envelope=lo_noise_envelope_controls()
    rf_startup=live_rf_startup_controls()
    lo_payload=connected_lo_payload()
    allocation_load=allocation_load_controls(lo_payload)
    host_clock_edges=host_clock_edge_controls()
    receiver_estimation=receiver_estimation_controls()
    rf_noise_placement=rf_noise_placement_controls()
    external_filter_convergence=external_filter_convergence_controls()
    external_receive=external_receive_controls()
    external_payload=external_receive_payload()
    combined_clock=next(row for row in lo_reference_phase['cases'] if row['bandwidth_hz']==2e6)
    combined_lo_config=dict(bandwidth_hz=combined_clock['bandwidth_hz'],max_step_s=6.25e-9,
        noise_tones=combined_clock['oscillator_noise_tones'],
        detector_phase_tones=combined_clock['detector_phase_tones'])
    external_combined_payload=external_receive_payload(lo_configuration=combined_lo_config)
    he20_capture_cache={}
    he20_combined=connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1','combined_clock_0.25','combined_no_converter_jitter',
                     'combined_no_detector_phase','combined_no_fifo_clock_charge'))
    he20_combined_gain=connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=1.25))
    assert all(row['conditional_quality_pass'] for row in he20_combined_gain['cases'])
    he20_independent=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=1.25),remote_clock_ppm=ppm)
        for ppm in (0.,-100.,100.)]
    he20_pilot_timing=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=1.5),
        remote_clock_ppm=ppm,pilot_timing=True) for ppm in (0.,-100.,100.)]
    assert any(not row['conditional_quality_pass'] for result in he20_pilot_timing for row in result['cases'])
    he20_matched_gain=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=1.5),
        remote_clock_ppm=ppm) for ppm in (0.,-100.,100.)]
    he20_sinc=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,combined_lo_config=combined_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=1.5),
        remote_clock_ppm=ppm,pilot_timing=True,receiver_sinc=True) for ppm in (0.,-100.,100.)]
    he20_training_rate=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=1.5),remote_clock_ppm=ppm,training_rate=True,
        receiver_sinc=sinc) for sinc in (False,True) for ppm in (-100.,0.,100.)]
    he20_combined_recovery=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=1.5),remote_clock_ppm=-100.,training_rate=True,
        pilot_timing=True,receiver_sinc=sinc) for sinc in (False,True)]
    he20_refined_recovery=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=1.5),remote_clock_ppm=ppm,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=subdivisions)
        for ppm,subdivisions in ((-100.,4),(-100.,16),(0.,16),(100.,16))]
    assert all(row['conditional_quality_pass'] for result in he20_refined_recovery for row in result['cases'])
    he20_payload_diversity=[connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=1.5),remote_clock_ppm=0.,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=16,payload_seed=seed)
        for seed in (952,953,954)]
    assert any(not row['conditional_quality_pass'] for result in he20_payload_diversity for row in result['cases'])
    assert not any(row['decision_accepts_quality_failure'] for result in he20_payload_diversity for row in result['cases'])
    he20_gain_headroom=connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=2.),remote_clock_ppm=0.,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=16,payload_seed=952)
    assert all(row['conditional_quality_pass'] and row['transport']['adc_clips']==0
               for row in he20_gain_headroom['cases'])
    he20_input_noise=connected_he20_payload(capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=2.),remote_clock_ppm=0.,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=16,payload_seed=952,
        frontend_input_referred=True)
    assert all(not row['conditional_quality_pass'] for row in he20_input_noise['cases'])
    wider_clock=next(row for row in lo_reference_phase['cases'] if row['bandwidth_hz']==2.5e6)
    wider_lo_config=dict(bandwidth_hz=2.5e6,max_step_s=6.25e-9,
        noise_tones=wider_clock['oscillator_noise_tones'],detector_phase_tones=wider_clock['detector_phase_tones'])
    he20_receiver_candidate=connected_he20_payload(capture_cache=he20_capture_cache,
        combined_lo_config=wider_lo_config,
        case_labels=('combined_clock_0.1',),settings_overrides=dict(rx_gain=2.),
        remote_clock_ppm=0.,training_rate=True,pilot_timing=True,receiver_sinc=True,
        external_substeps=16,payload_seed=953,channel_delays=tuple(range(-4,12)),
        decision_phase=True)
    assert all(row['conditional_quality_pass'] for row in he20_receiver_candidate['cases'])
    assert all(row['receiver_delivery']['payload_bits']==fixture('wifi_he20',seed=953).symbols.tolist()
               for row in he20_receiver_candidate['cases'])
    he20_receiver_failures=[connected_he20_payload(capture_cache=he20_capture_cache,
        combined_lo_config=wider_lo_config,case_labels=('combined_clock_0.1',),
        settings_overrides=dict(rx_gain=2.),remote_clock_ppm=0.,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=16,payload_seed=953,
        channel_delays=tuple(range(-4,12)),decision_phase=True,remote_fault=fault)
        for fault in ('tail_erasure','late_phase_step','silence','training_erasure')]
    assert all(not row['conditional_quality_pass'] and not row['receiver_delivery']['qualified']
               and not row['receiver_delivery']['payload_bits']
               for result in he20_receiver_failures for row in result['cases'])

    he20_noise_diagnosis=connected_he20_payload(frontend_input_referred=False,capture_cache=he20_capture_cache,
        combined_lo_config=combined_lo_config,case_labels=('combined_no_converter_jitter',
            'combined_no_detector_phase','combined_no_fifo_clock_charge',
            'combined_no_additive_noise','combined_no_residual_phase','combined_no_oscillator_noise'),
        settings_overrides=dict(rx_gain=1.5),remote_clock_ppm=0.,training_rate=True,
        pilot_timing=True,receiver_sinc=True,external_substeps=16,payload_seed=952)
    assert any(row['comparison']=='combined_clock_0.1' and row['offset_hz']==0.
               and not row['conditional_quality_pass'] for row in he20_combined['cases'])
    usb_response=usb_observed_response(request_lengths=(23,61,512,4096))
    usb_paced_response=usb_observed_response(request_lengths=(4096,),host_pacing=True)
    usb_coalesced_response=usb_observed_response(request_lengths=(23,61,512,4096),
        host_pacing=True,coalesce_return=True)
    assert all(row.get('delivered',False) for row in usb_coalesced_response['cases'])
    assert any(row.get('fault')=='Playback overflow' for row in usb_response['cases'])
    assert all(row.get('delivered',False) for row in usb_paced_response['cases'])
    usb_independent_phases=usb_observed_response(request_lengths=(512,),host_pacing=True,
        coalesce_return=True,clock_phases=tuple((a,b) for a in (0.,.37,.83) for b in (0.,.37,.83)))
    assert all(row.get('delivered',False) for row in usb_independent_phases['cases'])
    usb_response_split=usb_observed_response(request_lengths=(23,),split_time=True)
    assert usb_response_split['cases']==[row for row in usb_response['cases'] if row['request_bits']==23]
    usb_playback=raw_record_playback_controls()
    usb_observed_records=usb_observed_boundaries()
    usb_staged_trace=usb_staged_response_trace()
    usb_bidirectional_trace=usb_staged_response_trace(d2h_cdc=True)
    usb_commit_sensitivity=[usb_staged_response_trace(d2h_cdc=True,commit_beats=n) for n in (0,1)]
    usb_record_boundary_traces=[usb_staged_response_trace(d2h_cdc=True,record_tail_bits=n) for n in (0,10,20,30)]
    usb_fused_sensitivity=[usb_staged_response_trace(d2h_cdc=True,commit_beats=n,
        fused_d2h_snapshot=True) for n in (0,1,2)]
    external_lora=external_lora_payload()
    external_combined_lora=external_lora_payload(lo_configuration=combined_lo_config)
    host_staging=host_block_staging_controls()
    host_cdc=host_cdc_controls()
    block_clock_charge=block_clock_charge_controls()
    connected_lora=connected_lora_payload()
    connected_phase=connected_phase_payload()
    connected_he20=connected_he20_payload(capture_cache=he20_capture_cache,)
    numeric_gfsk=dict(wide_prefix=connected_numeric_gfsk(contract),matched_prefix=connected_numeric_gfsk(contract,matched_prefix=True))
    shared_controls=shared_rail_controls()
    host_coupling=host_coupling_screen(contract)
    ripple_cases=supply_ripple_screen(contract)
    tradeoffs=bandwidth_tradeoff(contract)
    blockers=blocker_screen(contract)
    handovers=exclusive_handover_check()
    report=dict(status='passed',fractional_divider_phase_screen=fractional_divider_phase_screen(),raw_host_clock_recovery=raw_clock_recovery,raw_host_reference_recovery=raw_reference_recovery,raw_host_alignment=raw_alignment,shared_rail_controls=shared_controls,rf_transmit_without_rx=rf_tx_only,retained_rf_recovery=rf_recovery,connected_numeric_gfsk=numeric_gfsk,connected_he20_payload=connected_he20,connected_phase_payload=connected_phase,connected_lora_payload=connected_lora,aligned_reference_recovery=aligned_recovery,aligned_reference_cancellation=aligned_cancel,aligned_host_delivery=aligned_delivery,observed_frame_alignment=alignment,cdr_qualification_controls=qualification,cold_cdr_host_delivery=cold_delivery,cdr_host_delivery=wired_delivery,usb_pad_lifecycle=usb_lifecycle,connected_gfsk_payload=connected_payload,live_rf_roundtrip=dict(samples=len(adc_packed),host_payload_identity=True,chunk_invariant=True,underflow_prevents_conversion=True),coverage=behavioral_coverage(contract,scenarios,expanded),host_coupling_screen=host_coupling,supply_ripple_screen=ripple_cases,bandwidth_tradeoff=tradeoffs,blocker_screen=blockers,exclusive_handovers=handovers,transition_cdr=cdr,embedded_clock_holdover=holdover,forwarded_timing_negative_control=timing_failure,burst_robustness=bursts,rf_distortion_diagnostics=distortion,carrier_offset_diagnostics=offsets,configuration_sweep=expanded,waveform_controls=dict(repeatable=True,overdrive=overdrive,rail_sag=sag), feedback_controls=feedback_cases,feedback_loss_control=lost,feedback_insufficient_capacity=insufficient,directional_drift_controls=drift_cases, elapsed_s=time.monotonic()-started, scenarios=scenarios,
        source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        planned_terminals=len(contract['pins']), terminal_limit=contract['limits']['total_terminals'],
        allocated_area_um2=sum(contract['area_um2'].values()), core_limit_um2=contract['limits']['core_area_um2'],
        full_chip_closure=False, physical_qualification=False,
        checks=['early traffic rejected','active reconfiguration rejected','stale epoch rejected','reference-loss restart','host-pause overflow','RX/TX bit conservation','chunk-invariant continuous queues','explicit stop discard accounting','simultaneous RX/TX','TX starvation and pause failure','bidirectional-pad duplex rejection','uncertainty failure controls','delayed quantized feedback','feedback chunk invariance','report-loss timeout','feedback cannot exceed host capacity'],
        remaining=['Feedback ABI/RTL mapping, calibration and real service envelopes','Unify persistent conversion/filter/host paths with independent acquisition and quality observers for all target classes','Dynamic supply-disturbance and thermal envelopes','calibration/retune and turnaround','multi-chip alignment','physical parameter evidence'])
    report['reference_presence']=reference_presence
    report['lo_clock_controls']=lo_controls
    report['lo_supply_controls']=lo_supply
    report['exclusive_transport_controls']=exclusive_transport
    report['timed_rf_lifecycle_controls']=timed_lifecycle
    report['converter_timing_controls']=converter_timing
    report['lo_integration_controls']=lo_integration
    report['host_activity_controls']=host_activity
    report['lo_reference_phase_controls']=lo_reference_phase
    report['lo_noise_envelope_controls']=lo_noise_envelope
    report['live_rf_startup_controls']=rf_startup
    report['connected_lo_payload']=lo_payload
    report['allocation_load_controls']=allocation_load
    report['host_clock_edge_controls']=host_clock_edges
    report['receiver_estimation_controls']=receiver_estimation
    report['rf_noise_placement']=rf_noise_placement
    report['external_filter_convergence']=external_filter_convergence
    report['external_receive_controls']=external_receive
    report['external_receive_payload']=external_payload
    report['external_receive_combined_noise']=external_combined_payload
    report['he20_combined_noise']=he20_combined
    report['he20_combined_gain']=he20_combined_gain
    report['he20_independent_clock']=he20_independent
    report['he20_pilot_timing']=he20_pilot_timing
    report['he20_matched_gain']=he20_matched_gain
    report['he20_sinc_comparison']=he20_sinc
    report['he20_receiver_failures']=he20_receiver_failures
    report['he20_receiver_candidate']=he20_receiver_candidate
    report['he20_input_referred_noise']=he20_input_noise
    report['he20_gain_headroom']=he20_gain_headroom
    report['he20_noise_diagnosis']=he20_noise_diagnosis
    report['he20_payload_diversity']=he20_payload_diversity
    report['he20_refined_recovery']=he20_refined_recovery
    report['he20_training_rate_comparison']=he20_training_rate
    report['he20_combined_recovery']=he20_combined_recovery
    report['usb_observed_response']=usb_response
    report['usb_paced_response']=usb_paced_response
    report['usb_coalesced_response']=usb_coalesced_response
    report['usb_independent_clock_phases']=usb_independent_phases
    report['usb_response_split_equivalence']=True
    report['raw_record_playback']=usb_playback
    report['usb_observed_boundaries']=usb_observed_records
    report['usb_staged_response_trace']=usb_staged_trace
    report['usb_bidirectional_response_trace']=usb_bidirectional_trace
    report['usb_commit_latency_sensitivity']=usb_commit_sensitivity
    report['usb_fused_snapshot_sensitivity']=usb_fused_sensitivity
    report['usb_record_boundary_traces']=usb_record_boundary_traces
    report['external_lora_payload']=external_lora
    report['external_lora_combined_noise']=external_combined_lora
    report['host_block_staging_controls']=host_staging
    report['host_cdc_controls']=host_cdc
    report['block_clock_charge_controls']=block_clock_charge
    report['wired_reference_presence']=wired_reference_presence
    (P/'evidence/behavioral-system.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],scenarios=len(scenarios),generic_configurations=len(expanded),elapsed_s=report['elapsed_s'],full_chip_closure=False)))


if __name__ == '__main__':
    run()
