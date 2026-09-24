"""Whole-chip architecture screening without analog ODE integration.

Protocol names exist only in the external scenario runner. Quality equations are
conditional budgets, not modem simulation or standards-compliance verdicts.
"""
from dataclasses import dataclass, asdict, replace
from collections import deque
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
from stream_codec import slots
from lane_group import forwarded_pll_acquisition
from protocol_pad import SharedWiredPad, usb_nrzi, usb_decode, usb_framed_turnaround
from resource_configuration import decode_resource_word, encode_resource_word, validate_wire_timing, validate_rf_settings


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
        core=SampledRFStream(settings,offset_hz=offset_hz,seed=seed,clock_scale=self.a.source_clock_scale,**impairments)
        epoch=self.epoch
        def produce(index):
            if self.state!='active' or self.epoch!=epoch or core.index!=index:
                raise ValueError('Stale or misaligned RF sample event')
            value=core.process([input_source(index)])[0]
            bits=settings['converter_bits'];scale=1<<(bits-1);mask=(1<<bits)-1
            return (int(round(value.real*scale))&mask) | ((int(round(value.imag*scale))&mask)<<bits)
        self.rf_stream=core;self.rf_source=produce

    def start(self):
        if self.resources is None or self.state != 'reset':
            raise ValueError('Configured reset state required')
        self.state = 'acquiring'
        self.ready_at = self.time + self.a.startup_s

    def advance(self, end):
        if not math.isfinite(end) or end < self.time:
            raise ValueError('Monotonic event time required')
        if self.stream is not None and end!=self.time:
            raise ValueError('Advance active stream through transfer, or stop first')
        self.time = end
        if self.state == 'acquiring' and end >= self.ready_at:
            self.state = 'active'

    def stop(self):
        discarded=dict(rx_bits=self.stream['occupancy'] if self.stream else 0,
                       tx_bits=self.stream['tx_bits'] if self.stream else 0)
        self.stream=None
        if self.rf_stream is not None:self.rf_stream.reset()
        self.rf_stream=None;self.rf_source=None
        self.state = 'reset'
        self.ready_at = math.inf
        self.epoch += 1
        return discarded

    def lose_reference(self):
        return self.stop()

    def receive(self, **kwargs):
        return self.transfer(directions=('rx',), **kwargs)

    def transfer(self, *, mode, source_hz, sample_bits, frames=128, depth_bits=2048,
                 host_pause_frames=0, epoch, directions=('rx','tx'), tx_prefill_bits=512,
                 feedback=False, feedback_stop_after=None, rx_source=None, tx_source=None, tx_prefill_value=0, rx_event_time=None):
        if rx_source is None and 'rx' in directions and self.rf_source is not None:rx_source=self.rf_source
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
        if tx_source is not None and (not callable(tx_source) or 'tx' not in directions):
            raise ValueError('TX word source requires enabled transmit service')
        if type(tx_prefill_value) is not int or not 0<=tx_prefill_value<(1<<tx_prefill_bits):
            raise ValueError('TX prefill value must fit prefill bit count')
        if rx_event_time is not None and (not callable(rx_event_time) or directions!=('rx',)):
            raise ValueError('Recovered source timing currently requires RX-only service')
        plan = slots(mode, self.resources['frame_words'])
        name = 'iq' if self.resources['engine'] == 'rf' else 'wire'
        host_hz = (250e6 if mode == 0 else 312.5e6) * self.a.host_clock_scale
        rate = source_hz * self.a.source_clock_scale
        signature=(mode,source_hz,sample_bits,depth_bits,tuple(directions),tx_prefill_bits,host_pause_frames,feedback,feedback_stop_after,rx_source,tx_source,tx_prefill_value,rx_event_time)
        if self.stream is not None and self.stream['signature']!=signature:
            raise ValueError('Stop before changing stream geometry or prefill')
        if self.stream is None:
            initial=tx_prefill_bits if 'tx' in directions else 0
            self.stream=dict(signature=signature,origin=self.time,frame=0,
                occupancy=0,produced=0,returned=0,high=0,sample_index=0,rx_slot=0,tx_slot=0,rx_quota=0,tx_quota=0,
                tx_bits=initial,tx_min=initial,tx_high=initial,tx_in=0,tx_out=0,
                reports=deque(),snapshot=None,last_report=None,reports_received=0,quota_phase=0.,last_source_time=-math.inf,next_source_time=None)
            if rx_source is not None:self.stream.update(rx_buffer=0,rx_words=[])
            if tx_source is not None:self.stream.update(tx_buffer=tx_prefill_value,tx_samples=[])
        state=self.stream
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
        while True:
            if rx_event_time is None:source_time=sample_index/rate
            else:
                if state['next_source_time'] is None:
                    candidate=rx_event_time(sample_index)
                    if not math.isfinite(candidate) or candidate<0 or candidate<=state['last_source_time']:
                        raise ValueError('Recovered sample times must be finite and strictly increasing')
                    state['next_source_time']=candidate
                source_time=state['next_source_time']
            now,kind=min((source_time,0),
                (rx_slot/rx_hz if 'rx' in directions or feedback else math.inf,1),
                (tx_slot/tx_hz if 'tx' in directions else math.inf,2),
                (state['reports'][0][0] if state['reports'] else math.inf,3))
            if now>=end:
                now=end;break
            if kind==0:
                if 'tx' in directions and tx_bits<sample_bits:
                    fault='underflow';break
                if 'rx' in directions:
                    if occupancy+sample_bits>depth_bits:
                        fault='overflow';break
                    if rx_source is not None:
                        value=rx_source(sample_index)
                        if type(value) is not int or not 0<=value<(1<<sample_bits):
                            raise ValueError('RX sample must fit configured unsigned packing width')
                        state['rx_buffer']|=value<<occupancy
                    occupancy+=sample_bits;produced+=sample_bits;high=max(high,occupancy)
                if 'tx' in directions:
                    if tx_bits<sample_bits:
                        fault='underflow';break
                    if tx_source is not None:
                        state['tx_samples'].append(state['tx_buffer']&((1<<sample_bits)-1))
                        state['tx_buffer']>>=sample_bits
                    tx_bits-=sample_bits;tx_out+=sample_bits;tx_min=min(tx_min,tx_bits)
                state['next_source_time']=None
                state['last_source_time']=source_time
                sample_index+=1
            elif kind==1:
                frame,slot=divmod(rx_slot,len(plan))
                if slot==0:
                    quota=min(plan.count(name),occupancy//10) if frame>=host_pause_frames else 0
                    if feedback:state['snapshot']=(now,math.ceil(tx_bits*255/depth_bits),self.epoch)
                if slot==4 and feedback and (feedback_stop_after is None or frame<feedback_stop_after):
                    # Proposed occupancy use of the existing 8-bit header argument.
                    # Frame serialization plus two frame periods of external latency.
                    if len(state['reports'])>=16:
                        fault='telemetry_overflow';break
                    state['reports'].append((now+2*len(plan)/rx_hz,*state['snapshot']))
                if plan[slot]==name and quota:
                    if rx_source is not None:
                        state['rx_words'].append(state['rx_buffer']&1023)
                        state['rx_buffer']>>=10
                    occupancy-=10;returned+=10;quota-=1
                rx_slot+=1
            elif kind==2:
                frame,slot=divmod(tx_slot,len(plan))
                if slot==0:
                    tx_quota=min(plan.count(name),math.floor((frame+1)*nominal_words_per_frame)-math.floor(frame*nominal_words_per_frame))
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
                if plan[slot]==name and tx_quota:
                    if tx_bits+10>depth_bits:
                        fault='tx_overflow';break
                    if tx_source is not None:
                        value=tx_source(tx_in//10)
                        if type(value) is not int or not 0<=value<1024:
                            raise ValueError('TX host payload must fit ten bits')
                        state['tx_buffer']|=value<<tx_bits
                    tx_bits+=10;tx_in+=10;tx_quota-=1;tx_high=max(tx_high,tx_bits)
                tx_slot+=1
            else:
                _,captured,code,report_epoch=state['reports'].popleft()
                if report_epoch!=self.epoch:
                    fault='stale_feedback_epoch';break
                state['last_report']=(captured,code);state['reports_received']+=1
        self.time=state['origin']+now
        state.update(frame=end_frame,occupancy=occupancy,produced=produced,returned=returned,
            high=high,sample_index=sample_index,rx_slot=rx_slot,tx_slot=tx_slot,
            rx_quota=quota,tx_quota=tx_quota,tx_bits=tx_bits,tx_min=tx_min,
            tx_high=tx_high,tx_in=tx_in,tx_out=tx_out)
        assert produced == returned + occupancy
        assert (tx_prefill_bits if "tx" in directions else 0)+tx_in==tx_out+tx_bits
        if fault:
            self.state = 'fault'
        return dict(fault=fault, directions=list(directions),
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
        self.state=0j

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
        self.feed=(self.decay-1)/self.poles
        self.reset()

    def reset(self):
        self.state=np.zeros(len(self.poles),complex)

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
    """Persistent uniform-grid RF core; no packet observer or host queue yet."""
    def __init__(self,settings,*,offset_hz=0.,noise_rms=.001,seed=81,blocker_v=0.,blocker_hz=0.,saturation_v=None,ripple_v=0.,ripple_hz=1e6,lo_supply_hz_per_v=0.,clock_scale=1.):
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
        self.offset_hz=offset_hz;self.noise_rms=noise_rms;self.seed=seed
        self.reset()

    def reset(self):
        s=self.settings
        self.tx=EnvelopeFilter(self.actual_sample_hz,s['tx_cutoff_hz'])
        self.rx=MultipoleEnvelope(self.actual_sample_hz,s['rx_cutoff_hz'],s['rx_filter_order'])
        self.previous_tx=0j;self.index=0
        self.rng=np.random.default_rng(self.seed)
        self.dac_clips=0;self.adc_clips=0

    @staticmethod
    def quantize(values,bits=12):
        step=2/(1<<bits)
        clips=int(np.count_nonzero((abs(values.real)>1)|(abs(values.imag)>1)))
        output=np.rint(np.clip(values.real,-1,1-step)/step)*step+1j*np.rint(np.clip(values.imag,-1,1-step)/step)*step
        return output,clips

    def process(self,values):
        values=np.asarray(values,complex)
        if values.ndim!=1 or not np.all(np.isfinite(values)):
            raise ValueError('Finite one-dimensional converter samples required')
        if not len(values):return values.copy()
        dac,clips=self.quantize(values,self.settings['converter_bits']);self.dac_clips+=clips
        tx=self.tx.process(dac)
        drive=np.r_[self.previous_tx,tx[:-1]];self.previous_tx=complex(tx[-1])
        times=(self.index+np.arange(len(values)))/self.actual_sample_hz
        self.index+=len(values)
        drive=drive*np.exp(2j*math.pi*self.offset_hz*times)+self.blocker_v*np.exp(2j*math.pi*self.blocker_hz*times)
        ripple=self.ripple_v*np.sin(2*math.pi*self.ripple_hz*times)
        phase=self.lo_supply_hz_per_v*self.ripple_v/self.ripple_hz*(1-np.cos(2*math.pi*self.ripple_hz*times))
        drive*=np.exp(1j*phase)
        if self.saturation_v is not None:drive,_=compress_envelope(drive,self.saturation_v)
        output=self.rx.process(drive)*self.settings['rx_gain']*(1+ripple/3.3)
        # Draw paired quadratures per sample, independent of chunk boundaries.
        noise=self.rng.normal(size=(len(values),2))*self.noise_rms/math.sqrt(2)
        output+=noise[:,0]+1j*noise[:,1]
        adc,clips=self.quantize(output,self.settings['converter_bits']);self.adc_clips+=clips
        return adc


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


def waveform_screen(wave, a, power, *, seed=81, settings=None, carrier_offset_hz=0., recover_carrier=False, blocker=None, rx_order=None, frontend_saturation_v=None, supply_ripple=None):
    """Seeded sampled-envelope screen; no RF carrier or analog ODE integration.

    Selectable conversion, ZOH source contract, causal one-pole TX/RX
    filter hypotheses. Separate known prefix drives FPGA delay/gain acquisition.
    """
    if not math.isfinite(carrier_offset_hz):raise ValueError('Finite carrier offset required')
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
    payload_count=math.ceil(len(x)/wave.sample_hz*converter_hz)
    count=payload_count
    ratio=Fraction(str(wave.sample_hz))/Fraction(str(converter_hz))
    indices=np.fromiter((i*ratio.numerator//ratio.denominator for i in range(count)),dtype=np.int64,count=count)
    source=x[np.minimum(indices,len(x)-1)]
    repetition=32 if converter_hz<10e6 else 64
    training_rng=np.random.default_rng(912)
    training=amplitude*np.repeat(np.exp(1j*(np.pi/4+np.pi/2*training_rng.integers(0,4,repetition//4))),4)
    training=np.tile(training,512//repetition)
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
    mixer_input=np.r_[0j,tx[:-1]]*np.exp(2j*math.pi*carrier_offset_hz*np.arange(count)/converter_hz)
    if blocker is not None:
        offset=blocker['offset_hz'];level=blocker['relative_power_db']
        if not math.isfinite(offset) or not math.isfinite(level) or abs(offset)>=converter_hz/2:
            raise ValueError('Finite blocker strictly inside converter Nyquist interval required')
        mixer_input+=amplitude*10**(level/20)*np.exp(2j*math.pi*offset*np.arange(count)/converter_hz)
    ripple_v=np.zeros(count)
    ripple_phase=np.zeros(count)
    if supply_ripple is not None:
        amplitude_v=supply_ripple['amplitude_v'];frequency=supply_ripple['frequency_hz']
        sensitivity=supply_ripple['lo_sensitivity_hz_per_v']
        if (not all(math.isfinite(v) for v in (amplitude_v,frequency,sensitivity)) or
                not 0<=amplitude_v<power['estimated_rail_v']['RF'] or
                not 0<frequency<converter_hz/2):
            raise ValueError('Invalid supply ripple envelope')
        ripple_time=np.arange(count)/converter_hz
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
    filtered=multipole_envelope(mixer_input,converter_hz,settings['rx_cutoff_hz'],rx_order)
    times=(np.arange(count)+1)/converter_hz
    jitter=rng.normal(0,a.sample_jitter_s,count)
    sampled=(np.interp(times+jitter,np.r_[0.,times],np.r_[0.,filtered.real])+
             1j*np.interp(times+jitter,np.r_[0.,times],np.r_[0.,filtered.imag]))
    phase=rng.normal(0,a.relative_lo_phase_rms_rad,count)
    gain=power['estimated_rail_v']['RF']/a.supply_v*settings['rx_gain']
    z=(gain+settings['rx_gain']*ripple_v/a.supply_v)*sampled*np.exp(1j*phase)
    frontend_sigma=amplitude*a.frontend_evm_rms/math.sqrt(2)
    # ENOB is represented by input-referred white noise beyond ideal 12-bit ADC.
    adc_sigma=math.sqrt(max(0.,(2**(1-a.converter_enob))**2-step**2)/12)
    sigma=math.hypot(frontend_sigma,adc_sigma)
    z+=sigma*(rng.normal(size=count)+1j*rng.normal(size=count))
    received,adc_clipped=quantize(z)
    carrier=dict(enabled=recover_carrier,acquired=False,estimate_hz=None,
                 capture_limit_hz=converter_hz/(2*repetition),repetition_samples=repetition)
    if recover_carrier:
        try:
            estimate,coherence=repeated_training_frequency(received[256:256+2*repetition],repetition,converter_hz)
            # Refine over seven settled repeats using phase progression; coarse
            # derotation keeps the phase slope unambiguous within capture range.
            blocks=received[64:512].reshape(-1,repetition)
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
    raw=(np.interp(observer_times,times,received.real)+1j*np.interp(observer_times,times,received.imag))
    raw_evm=float(np.sqrt(np.mean(abs(raw-x)**2)/np.mean(abs(x)**2)))
    if acquisition['acquired']:observer_times+=acquisition['delay_s']
    received=(np.interp(observer_times,np.r_[0.,times],np.r_[0.,received.real])+
              1j*np.interp(observer_times,np.r_[0.,times],np.r_[0.,received.imag]))
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
        converter_hz=converter_hz,rx_filter_order=rx_order,supply_ripple=supply_ripple,peak_supply_phase_rad=float(np.max(abs(ripple_phase))),blocker=blocker,frontend_compression=compression,carrier_offset_hz=carrier_offset_hz,carrier_recovery=carrier,dac_updates=count,adc_samples=count,
        tx_filter_cutoff_hz=settings['tx_cutoff_hz'],rx_filter_cutoff_hz=settings['rx_cutoff_hz'],rx_gain=settings['rx_gain'],
        timing_recovery=acquisition,unaligned_evm_rms=raw_evm,fixture_samples=len(x),fixture_sample_hz=wave.sample_hz,duration_s=wave.duration,training_and_guard_s=544/converter_hz+(len(block_training)/wave.sample_hz if block_training is not None else 0),
        raw_received_rms_v=float(np.sqrt(np.mean(abs(raw)**2))),received_rms_v=float(np.sqrt(np.mean(abs(received)**2))),rf_rail_gain=gain,seed=seed,conditional_screen_pass=(not recover_carrier or carrier['acquired']) and acquisition['acquired'] and (equalized is None or equalized['acquired']) and quality_evm<=.10 and quality_errors==0,
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
        word=0
        for j in range(10):
            i=self.bit_index;self.phase+=self.frequency+self.correction;self.gap+=1
            # One-UI detector latency: only completed channel intervals inform correction.
            crossing=self.crossing(i-1)
            if crossing is not None:
                self.detected_edges+=1
                error=(self.phase-crossing+self.rng.normal(0,5e-12*self.rate)+.5)%1-.5
                self.correction=float(np.clip(self.correction-.0002*error/self.gap,-.002,.002))
                self.phase-=.15*error;self.gap=0
                self.edge_errors.append(abs(error))
            if self.gap>64:self.edge_errors.clear()
            qualified=(len(self.edge_errors)==64 and max(self.edge_errors)<.1)
            if self.timing_qualified and not qualified:self.qualification_losses+=1
            self.timing_qualified=qualified
            if qualified and self.first_qualified_bit is None:self.first_qualified_bit=i
            word|=int(self.voltage(i+.5+self.phase)>0)<<j
            timestamp=(i+.5+self.phase)/self.rate
            self.bit_index+=1
        self.pending=word
        return timestamp

    def consume(self,index):
        if index!=self.word_index or self.pending is None:raise ValueError('No current CDR word')
        value=self.pending;self.pending=None;self.word_index+=1;self.words.append(value)
        return value


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
    bits=np.random.default_rng(43).integers(0,2,2040).tolist()+[0]*1000
    burst=RecoveredWordSource(bits,2.5e9,.35,100.)
    for i in range(204):burst.forecast(i);burst.consume(i)
    assert burst.timing_qualified
    for i in range(204,304):burst.forecast(i);burst.consume(i)
    assert not burst.timing_qualified and burst.qualification_losses>=1
    return dict(silence_rejected=True,transition_loss_revokes_qualification=True,
        window_edges=64,max_phase_error_ui=.1,max_gap_bits=64,
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


def connected_gfsk_payload(bits=12):
    if bits not in (8,12):raise ValueError('Supported converter precision required')
    scale=1<<(bits-1);modulus=1<<bits;mask=modulus-1;width=2*bits
    mode=1 if bits==8 else 0
    host_hz=312.5e6 if mode else 250e6
    prefix=np.random.default_rng(913).integers(0,2,32)
    payload=np.random.default_rng(37).integers(0,2,64)
    wave=gfsk(np.r_[prefix,payload],fs=20e6)
    known_prefix=gfsk(prefix,fs=20e6)
    settings=dict(sample_hz=20e6,tx_cutoff_hz=10e6,rx_cutoff_hz=2.5e6,rx_filter_order=5,converter_bits=bits)
    samples=np.r_[np.zeros(73),wave.samples*.2,np.zeros(128)]
    codes=[int(round(z.real*scale))%modulus | ((int(round(z.imag*scale))%modulus)<<bits) for z in samples]
    stream=sum(value<<(width*i) for i,value in enumerate(codes))
    def unpack(value):
        i=value&mask;q=(value>>bits)&mask
        return ((i if i<scale else i-modulus)+1j*(q if q<scale else q-modulus))/scale
    results=[]
    for offset in (-48000.,0.,48000.):
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='rf',rf=settings)
        chip.attach_rf_stream(lambda index:unpack(chip.stream['tx_buffer']&((1<<width)-1)),offset_hz=offset)
        chip.start();chip.advance(chip.ready_at)
        frames=math.ceil((len(samples)+256)/20e6*host_hz/64)
        flow=chip.transfer(mode=mode,source_hz=20e6,sample_bits=width,epoch=0,frames=frames,
            tx_prefill_value=stream&((1<<512)-1),tx_source=lambda index:(stream>>(512+10*index))&1023)
        assert flow['fault'] is None and flow['returned_bits']>=len(samples)*width
        # Decode only words actually delivered to the host, never pending RX bits.
        returned=sum(word<<(10*i) for i,word in enumerate(chip.stream['rx_words']))
        observed=np.array([unpack((returned>>(width*i))&((1<<width)-1)) for i in range(len(samples))])
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


def usb_pad_lifecycle():
    """Electrical role/drive sequencing using the existing finite shared pad.

    Hold durations are model probes, not a USB attach/reset/chirp compliance trace.
    """
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
            local_and_peer_decode=True,released_squelch=True,turnaround=usb_framed_turnaround()))
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
    files=[Path(__file__),P/'spec/contract.json',P/'verification/stream_codec.py',P/'verification/transport_model.py',Path(__file__).with_name('resource_configuration.py'),P/'system_model/connected/protocol_signals.py',P/'system_model/connected/lane_group.py',P/'system_model/connected/sampled_pll.py',P/'system_model/connected/oscillator_noise.py',P/'system_model/connected/protocol_pad.py']
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
    live.stop()
    assert core.index==0 and live.rf_stream is None and live.rf_source is None
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
    usb_lifecycle=usb_pad_lifecycle()
    connected_payload=connected_gfsk_payload(12)+connected_gfsk_payload(8)
    host_coupling=host_coupling_screen(contract)
    ripple_cases=supply_ripple_screen(contract)
    tradeoffs=bandwidth_tradeoff(contract)
    blockers=blocker_screen(contract)
    handovers=exclusive_handover_check()
    report=dict(status='passed',cdr_qualification_controls=qualification,cold_cdr_host_delivery=cold_delivery,cdr_host_delivery=wired_delivery,usb_pad_lifecycle=usb_lifecycle,connected_gfsk_payload=connected_payload,live_rf_roundtrip=dict(samples=len(adc_packed),host_payload_identity=True,chunk_invariant=True,underflow_prevents_conversion=True),coverage=behavioral_coverage(contract,scenarios,expanded),host_coupling_screen=host_coupling,supply_ripple_screen=ripple_cases,bandwidth_tradeoff=tradeoffs,blocker_screen=blockers,exclusive_handovers=handovers,transition_cdr=cdr,embedded_clock_holdover=holdover,forwarded_timing_negative_control=timing_failure,burst_robustness=bursts,rf_distortion_diagnostics=distortion,carrier_offset_diagnostics=offsets,configuration_sweep=expanded,waveform_controls=dict(repeatable=True,overdrive=overdrive,rail_sag=sag), feedback_controls=feedback_cases,feedback_loss_control=lost,feedback_insufficient_capacity=insufficient,directional_drift_controls=drift_cases, elapsed_s=time.monotonic()-started, scenarios=scenarios,
        source_sha256={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        planned_terminals=len(contract['pins']), terminal_limit=contract['limits']['total_terminals'],
        allocated_area_um2=sum(contract['area_um2'].values()), core_limit_um2=contract['limits']['core_area_um2'],
        full_chip_closure=False, physical_qualification=False,
        checks=['early traffic rejected','active reconfiguration rejected','stale epoch rejected','reference-loss restart','host-pause overflow','RX/TX bit conservation','chunk-invariant continuous queues','explicit stop discard accounting','simultaneous RX/TX','TX starvation and pause failure','bidirectional-pad duplex rejection','uncertainty failure controls','delayed quantized feedback','feedback chunk invariance','report-loss timeout','feedback cannot exceed host capacity'],
        remaining=['Feedback ABI/RTL mapping, calibration and real service envelopes','Unify persistent conversion/filter/host paths with independent acquisition and quality observers for all target classes','Dynamic supply-disturbance and thermal envelopes','calibration/retune and turnaround','multi-chip alignment','physical parameter evidence'])
    (P/'evidence/behavioral-system.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],scenarios=len(scenarios),generic_configurations=len(expanded),elapsed_s=report['elapsed_s'],full_chip_closure=False)))


if __name__ == '__main__':
    run()
