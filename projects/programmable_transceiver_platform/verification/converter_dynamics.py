"""Closed-loop paired SAR requirement model and its shared-supply load.

Not identified GF180 devices: every pole, capacitor, current and noise value is
an explicit hypothesis. Comparator decisions generate subsequent trial codes
and reference charge; measured code/reference histories are never inputs.
"""
from dataclasses import dataclass, asdict
from copy import deepcopy
import math
import json
import numpy as np


@dataclass(frozen=True)
class SARParameters:
    acquisition_s: float = 5e-9
    bit_durations_s: tuple = (3e-9,2.6e-9,2.4e-9,2.1e-9,1.9e-9,1.6e-9,1.3e-9,1.1e-9,1e-9,1e-9)
    comparator_s: float = .5e-9
    reset_control_s: float = 2e-9
    sample_cap_per_leg_f: float = .5e-12
    sample_resistance_ohm: float = 200.
    dac_effective_cap_f: float = 1e-12
    dac_tau_s: float = .3e-9
    reference_cap_f: float = 100e-12
    reference_r_ohm: float = 50.
    reference_limit_a: float = .001
    reference_idle_a: float = .002
    comparator_noise_rms_v: float = .001
    temperature_k: float = 300.15
    diagnostic_input_cap_f: float = 0.
    diagnostic_series_resistance_ohm: float = 0.
    diagnostic_reference_effective_cap_per_lane_f: float = 0.
    unmodeled_cycle_uncertainty_s: float = 0.



def validate_sar_binding(environment, parameters, *, comparator_model=None):
    """A bound receiver cannot substitute a different converter behind its identity.

    None selects the explicitly simplified assigned-ENOB path. Independent
    mathematical environments may still supply arbitrary SAR examples.
    """
    if parameters is None:
        return
    if not isinstance(parameters,SARParameters):
        raise TypeError('SARParameters required for causal conversion')
    if not any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        return
    owned=environment.get('converter_parameters')
    actual=asdict(parameters)
    if not isinstance(owned,dict) or set(owned)!=set(actual):
        raise ValueError('Design-bound receiver requires complete converter parameters')
    # Serialization normalizes the tuple/list representation of the bit schedule.
    expected=json.loads(json.dumps(owned,allow_nan=False))
    actual=json.loads(json.dumps(actual,allow_nan=False))
    changed=sorted(key for key in actual if actual[key]!=expected[key])
    if changed:
        raise ValueError('SAR parameters conflict with design-bound environment: '+', '.join(changed))
    if comparator_model is not None:
        owned_comparator=environment.get('comparator_parameters')
        if not isinstance(owned_comparator,dict) or set(owned_comparator)!={'tau_s','launch_s','output_threshold_v'}:
            raise ValueError('Design-bound receiver requires complete comparator parameters')
        if comparator_model!=owned_comparator:
            raise ValueError('Comparator model conflicts with design-bound environment')


def parameters_from_inventory(architecture):
    """Selected ADC timing/loading allowances; other device laws remain hypotheses."""
    a=architecture['blocks']['adc_i']['parameters']
    q=architecture['blocks']['adc_q']['parameters']
    keys=('native_bits','acquisition_s','decision_s','reset_s','sample_cap_per_leg_f',
          'diagnostic_input_cap_budget_f','diagnostic_series_resistance_budget_ohm',
          'unmodeled_cycle_guard_s')
    if any(a[k]!=q[k] for k in keys):
        raise ValueError('Paired model requires matched ADC allocations')
    ref=architecture['blocks']['refbuf']['parameters']
    model=dict(architecture['model_assumptions']['paired_sar']['parameters'])
    model['bit_durations_s']=tuple(model['bit_durations_s'])
    owned=dict(reference_cap_f=ref['reservoir_f'],reference_r_ohm=ref['output_r_ohm'],
               reference_limit_a=ref['source_limit_a'],reference_idle_a=ref['quiescent_current_a'],
               acquisition_s=a['acquisition_s'],reset_control_s=a['reset_s'],
               sample_cap_per_leg_f=a['sample_cap_per_leg_f'],
               diagnostic_input_cap_f=a['diagnostic_input_cap_budget_f'],
               diagnostic_series_resistance_ohm=a['diagnostic_series_resistance_budget_ohm'],
               unmodeled_cycle_uncertainty_s=a['unmodeled_cycle_guard_s'],
               temperature_k=architecture['blocks']['board']['parameters']['nominal_temperature_c']+273.15)
    if set(model)&set(owned):
        raise ValueError('Duplicate ownership of converter parameters')
    model.update(owned)
    from dataclasses import fields
    if set(model)!={field.name for field in fields(SARParameters)}:
        raise ValueError('Shared design must resolve every converter parameter exactly once')
    p=SARParameters(**model)
    if a['native_bits']!=len(p.bit_durations_s):
        raise ValueError('Bit schedule differs from selected native precision')
    if not math.isclose(sum(p.bit_durations_s),a['decision_s'],abs_tol=1e-18):
        raise ValueError('Bit schedule differs from selected decision allowance')
    return p


def adc_switching_sources(*,sample_hz,mean_a,pulse_tau_s,harmonics=128,origin_s=0.,parameters=SARParameters()):
    """Assigned equal-charge ADC supply events; zero-mean five-port spectrum.

    Mean belongs inside the caller's DC allocation. This is a hypothesis for
    missing switch/comparator/control activity, not the reference recharge port.
    """
    p=parameters;durations=np.asarray(p.bit_durations_s,float)
    if not all(math.isfinite(x) for x in (sample_hz,mean_a,pulse_tau_s,origin_s)) or sample_hz<=0 or mean_a<0 or pulse_tau_s<=0:
        raise ValueError('Finite nonnegative charge and positive rate/pulse width required')
    if type(harmonics) is not int or not 1<=harmonics<=256 or durations.shape!=(10,) or np.any(durations<=p.comparator_s):
        raise ValueError('Ten valid SAR intervals and bounded harmonic count required')
    if 1/sample_hz<p.acquisition_s+sum(durations)+p.reset_control_s+p.unmodeled_cycle_uncertainty_s:
        raise ValueError('ADC schedule does not fit sample period')
    starts=np.r_[0.,np.cumsum(durations[:-1])]
    events=np.r_[-p.acquisition_s,starts,starts+durations-p.comparator_s,sum(durations)]+origin_s
    sources={}
    if mean_a==0:return sources
    for k in range(1,harmonics+1):
        frequency=k*sample_hz
        current=2*mean_a*np.mean(np.exp(-2j*np.pi*frequency*events))/(1+2j*np.pi*frequency*pulse_tau_s)**3
        sources[frequency]=np.array([0,-current,0,current,0])
    return sources


class ObservedGain:
    """Code-only FPGA gain policy plus causal command/PGA settling dynamics.

    Physical timestamps schedule propagation; the policy sees only completed
    ADC words. No source bits, packet boundary, wanted power or true gain target
    are available to its decisions. Analogue clipping uses supplied rail bounds.
    """
    def __init__(self,*,sample_hz,command_latency_s,acquisition_s,
                 headroom_start,headroom_end,initial_gain_db=40.,maximum_gain_db=60.,gain_codes_db=None,gain_response_tau_s=.2e-6):
        if not math.isfinite(gain_response_tau_s) or gain_response_tau_s<=0:
            raise ValueError('Positive finite PGA response time required')
        self.gain_response_tau_s=gain_response_tau_s
        self.gain_codes=None if gain_codes_db is None else tuple(gain_codes_db)
        self.minimum_gain_db=0. if self.gain_codes is None else min(self.gain_codes,default=0.)
        if self.gain_codes is not None and (not self.gain_codes or
                any(not math.isfinite(x) for x in self.gain_codes) or
                tuple(sorted(set(self.gain_codes)))!=self.gain_codes or
                initial_gain_db not in self.gain_codes or maximum_gain_db!=max(self.gain_codes)):
            raise ValueError('Ordered supported PGA codes, legal initial code and matching ceiling required')
        if not self.minimum_gain_db<=initial_gain_db<=maximum_gain_db or command_latency_s<0:
            raise ValueError('Bounded gain and nonnegative command latency required')
        self.window=round(sample_hz*1e-6);self.command_latency_s=command_latency_s
        self.acquisition_s=acquisition_s;self.headroom_start=np.asarray(headroom_start)
        self.headroom_end=np.asarray(headroom_end);self.maximum_gain_db=maximum_gain_db
        self.initial_gain_db=initial_gain_db;self.target_db=initial_gain_db
        self.gain=10**(initial_gain_db/20);self.time=None;self.pending=None
        self.energy=0.;self.clipped=0;self.updates=0;self.trace=[];self.commands=[]

    def advance(self,time):
        if self.time is None:self.time=time
        if time<self.time:raise ValueError('PGA state cannot travel backwards in time')
        if self.pending is not None and self.pending[0]<=time:
            when,target=self.pending
            self.gain=10**(self.target_db/20)+(self.gain-10**(self.target_db/20))*math.exp(-(when-self.time)/self.gain_response_tau_s)
            self.time=when;self.target_db=target;self.pending=None;self.updates+=1
        target=10**(self.target_db/20)
        self.gain=target+(self.gain-target)*math.exp(-(time-self.time)/self.gain_response_tau_s)
        self.time=time
        return self.gain

    def acquire(self,index,start,end,time):
        first=start*self.advance(time-self.acquisition_s)
        last=end*self.advance(time)
        self.trace.append(20*math.log10(self.gain))
        self.clipped+=int(abs(last.real)>self.headroom_end[index] or abs(last.imag)>self.headroom_end[index])
        def limit(value,bound):return complex(np.clip(value.real,-bound,bound),np.clip(value.imag,-bound,bound))
        return limit(first,self.headroom_start[index]),limit(last,self.headroom_end[index])

    def observe(self,index,code,available_s):
        self.advance(available_s)
        self.energy+=abs(code)**2
        if (index+1)%self.window==0:
            measured=math.sqrt(self.energy/self.window);self.energy=0.
            if self.pending is None:
                correction=float(np.clip(20*math.log10(.12/max(measured,1/512)),-6.,6.))
                target=float(np.clip(self.target_db+correction,self.minimum_gain_db,self.maximum_gain_db))
                if self.gain_codes is not None:target=min(self.gain_codes,key=lambda code:abs(code-target))
                apply_s=available_s+self.command_latency_s
                self.pending=(apply_s,target)
                self.commands.append(dict(last_observed_code=index,code_available_s=available_s,
                    earliest_apply_s=apply_s,target_gain_db=target))

    def report(self):
        return dict(gain_db=self.trace,pga_clipped_samples=self.clipped,applied_updates=self.updates,
            command_latency_s=self.command_latency_s,initial_gain_db=self.initial_gain_db,
            maximum_gain_db=self.maximum_gain_db,gain_codes_db=self.gain_codes,
            gain_response_tau_s=self.gain_response_tau_s,converter_bits=10,transport_bits=12,
            native_transport_low_two_bits_zero=True,commands=self.commands,
            scope='Completed native SAR codes drive bounded FPGA gain commands. Service delay begins after conversion availability; target changes propagate through the supplied PGA response pole. Instantaneous rail limits affect physical clipping, not the FPGA policy.')


def recover(reference, dac, target, code, duration, *, r, c, limit, tau):
    """Exact limited-RC reference recovery driving a first-order DAC output.

    A current-limited linear segment is followed by exponential recovery.
    Returned charge is signed charge delivered to the reference reservoir.
    """
    initial=reference;error=target-reference;direction=1. if error>=0 else -1.
    ramp=min(duration,max(0.,(abs(error)-limit*r)*c/limit))
    if ramp:
        slope=direction*limit/c;e=math.exp(-ramp/tau)
        dac=dac*e+code*(reference*(1-e)+slope*(ramp-tau*(1-e)))
        reference+=slope*ramp
    rest=duration-ramp
    if rest:
        tr=r*c;er=math.exp(-rest/tr);ed=math.exp(-rest/tau)
        cross=(rest/tau)*ed if abs(tr-tau)<1e-10*max(tr,tau) else tr/(tr-tau)*(er-ed)
        dac=dac*ed+code*(target*(1-ed)+(reference-target)*cross)
        reference=target+(reference-target)*er
    return reference,dac,c*(reference-initial)


def discharged_sar_state(*,parameters=SARParameters(),at_s=0.,seed=4901,comparator_model=None):
    """Explicit reset charge state, after rails are valid but before bias settles."""
    if not math.isfinite(at_s) or at_s<0:raise ValueError('Finite nonnegative reset time required')
    return dict(version=1,parameters=json.dumps(asdict(parameters),sort_keys=True),
        comparator_model=json.dumps(comparator_model,sort_keys=True),end_time_s=float(at_s),
        held=[0.,0.],reference_v=0.,dac=[0.,0.],last_code=[-1.,-1.],
        rng_state=np.random.default_rng(seed).bit_generator.state)


def paired_sar(values, starts, sample_times, reference_at, rail_at, *,
               parameters=SARParameters(), noise=True, seed=4901, input_control=None, initial_state=None, idle_step_s=None, comparator_model=None, input_test=(0,0)):
    """Sample/hold plus ten decisions, with one shared I/Q reference reservoir.

    Input endpoints describe a linear acquisition-window trajectory. Sample
    capacitors retain their preceding held input. Reference and DAC states
    persist across all bits and conversions. Reference source and DAC pole
    resistance scale as 3.3/local_rail: an assigned supply sensitivity.
    Optional continuation retains completed-conversion state and RNG position;
    idle forcing remains midpoint-held, not a continuous power-down model.
    """
    if len(input_test)!=2 or any(type(code) is not int or code not in (0,1,2,3) for code in input_test):
        raise ValueError('Two numeric ADC input-test codes required')
    input_test=tuple(input_test)
    if any(input_test) and input_control is not None:
        raise ValueError('ADC diagnostics bypass external gain feedback')
    if idle_step_s is not None and (not math.isfinite(idle_step_s) or idle_step_s<=0):
        raise ValueError('Positive finite idle integration step required')
    if comparator_model is not None:
        if set(comparator_model)!={'tau_s','launch_s','output_threshold_v'}:
            raise ValueError('Explicit comparator regeneration, launch and output threshold required')
        if (not all(math.isfinite(v) and v>0 for v in comparator_model.values())):
            raise ValueError('Positive finite comparator hypotheses required')
    comparator_identity=json.dumps(comparator_model,sort_keys=True)
    p=parameters;z=np.asarray(values,complex);start=np.asarray(starts,complex);t=np.asarray(sample_times,float)
    if (z.ndim!=1 or not len(z) or start.shape!=z.shape or t.shape!=z.shape or
            not np.all(np.isfinite(z)) or not np.all(np.isfinite(start)) or
            not np.all(np.isfinite(t)) or np.any(np.diff(t)<=0)):
        raise ValueError('Finite acquisition endpoints and increasing sampling times required')
    if (not all(math.isfinite(v) for k,v in asdict(p).items() if k!='bit_durations_s') or
            not all(math.isfinite(v) and v>0 for k,v in asdict(p).items()
                if k not in ('comparator_noise_rms_v','reference_idle_a','bit_durations_s',
                             'diagnostic_input_cap_f','diagnostic_series_resistance_ohm',
                             'diagnostic_reference_effective_cap_per_lane_f','unmodeled_cycle_uncertainty_s')) or
            min(p.comparator_noise_rms_v,p.reference_idle_a,p.diagnostic_input_cap_f,
                p.diagnostic_series_resistance_ohm,p.diagnostic_reference_effective_cap_per_lane_f,p.unmodeled_cycle_uncertainty_s)<0):
        raise ValueError('Positive physical hypotheses and a comparator interval inside each bit required')
    diagnostic_lanes=sum(code in (2,3) for code in input_test)
    if diagnostic_lanes*p.diagnostic_reference_effective_cap_per_lane_f>=p.reference_cap_f:
        raise ValueError('Diagnostic charge demand exhausts reference reservoir')
    durations=np.asarray(p.bit_durations_s,float)
    if durations.shape!=(10,) or not np.all(np.isfinite(durations)) or np.any(durations<=p.comparator_s):
        raise ValueError('Ten bit intervals longer than comparator allocation required')
    conversion_s=float(sum(durations));offsets=np.r_[0.,np.cumsum(durations[:-1])]
    required=p.acquisition_s+conversion_s+p.reset_control_s+p.unmodeled_cycle_uncertainty_s
    period=float(np.min(np.diff(t))) if len(t)>1 else required
    if period<required:
        raise ValueError('Conversion/acquisition/reset schedule does not fit the sampling period')
    # Reject incompatible retained state before consuming either forcing provider.
    previous_ends=np.r_[t[0]-p.acquisition_s,t[:-1]+conversion_s]
    if initial_state is not None:
        if (not isinstance(initial_state,dict) or initial_state.get('version')!=1 or initial_state.get('parameters')!=json.dumps(asdict(p),sort_keys=True) or
                initial_state.get('comparator_model')!=comparator_identity):
            raise ValueError('Compatible SAR continuation state required')
        end=float(initial_state['end_time_s'])
        if not math.isfinite(end) or t[0]-end<p.acquisition_s+p.reset_control_s+p.unmodeled_cycle_uncertainty_s-1e-18:
            raise ValueError('Continuation must allow acquisition/reset/cycle guard after the completed conversion')
        previous_ends[0]=end
    rng=np.random.default_rng(seed)
    retained=None
    if initial_state is not None:
        rng.bit_generator.state=initial_state['rng_state']
        held=complex(*initial_state['held']);reference=float(initial_state['reference_v'])
        dac=complex(*initial_state['dac']);last_code=complex(*initial_state['last_code'])
        if not all(np.isfinite(value) for value in (held,reference,dac,last_code)) or reference<0:
            raise ValueError('Finite retained SAR charge state and nonnegative reference required')
        retained=(held,reference,dac,last_code)
    # Reference forcing is midpoint-held over the DAC-settle and comparator
    # intervals, plus the inter-conversion interval; no truth reference samples.
    bit_start=t[:,None]+offsets
    settle=durations-p.comparator_s
    mid=np.stack((bit_start+settle/2,bit_start+settle+p.comparator_s/2),axis=-1)
    targets=np.asarray(reference_at(mid.ravel())).reshape(mid.shape)
    rails=np.asarray(rail_at(mid.ravel())).reshape(mid.shape)
    sample_ref=np.asarray(reference_at(t));sample_rails=np.asarray(rail_at(t))
    idle_mid=(previous_ends+t)/2
    idle_ref=np.asarray(reference_at(idle_mid));idle_rail=np.asarray(rail_at(idle_mid))
    if min(targets.min(),sample_ref.min(),idle_ref.min(),rails.min(),sample_rails.min(),idle_rail.min())<=0:
        raise ValueError('Positive reference and loaded rail required')
    thermal=math.sqrt(2*1.380649e-23*p.temperature_k/(p.sample_cap_per_leg_f+p.diagnostic_input_cap_f))
    # Draw per-conversion rows so extending the capture preserves the entire
    # earlier physical noise realization, including both I/Q components.
    draws=rng.normal(size=(len(z),22)) if noise else np.zeros((len(z),22))
    held_noise=thermal*(draws[:,0]+1j*draws[:,1])
    comparator_noise=p.comparator_noise_rms_v*(draws[:,2:12]+1j*draws[:,12:22])
    held=0j;reference=float(sample_ref[0]);initial_reference=reference
    last_code=-1-1j;dac=last_code*reference;last_time=float(previous_ends[0])
    if retained is not None:
        held,reference,dac,last_code=retained
        initial_reference=reference
    words=np.empty((len(z),2),np.int64)
    applied=np.empty_like(z)
    comparator_margins=np.empty((len(z),10,2))
    completion_times=np.empty(len(z));decision_durations=np.empty((len(z),10))
    # Each segment describes the exact reference recovery before the next load
    # event. It supports charge-preserving supply-current resampling downstream.
    segments=[];supply_observations=[];acquisition_references=[];decision_references=[];decision_observations=[];charge_drawn=0.;signed_recharge=0.;positive_recharge=0.
    diagnostic_charge=0.
    ref_min=reference;ref_max=reference;dac_error=0.;acq_error=[];peak_source=0.;limited_segments=0

    def advance(time,duration,target,rail,code):
        nonlocal reference,dac,signed_recharge,positive_recharge,peak_source,limited_segments,ref_min,ref_max
        supply_observations.append((time+duration/2,rail))
        r=p.reference_r_ohm*3.3/rail;tau=p.dac_tau_s*3.3/rail
        initial=reference
        peak_source=max(peak_source,min(p.reference_limit_a,max(0.,(target-reference)/r)))
        limited_segments+=int(abs(target-reference)/r>p.reference_limit_a)
        reference,dac,charge=recover(reference,dac,target,code,duration,
            r=r,c=p.reference_cap_f,limit=p.reference_limit_a,tau=tau)
        segments.append((time,duration,initial,target,r,charge))
        signed_recharge+=charge;positive_recharge+=max(0.,charge)
        ref_min=min(ref_min,initial,reference);ref_max=max(ref_max,initial,reference)

    def forcing_at(time):
        ref=float(np.asarray(reference_at(np.array([time])))[0])
        supply=float(np.asarray(rail_at(np.array([time])))[0])
        if not math.isfinite(ref) or not math.isfinite(supply) or min(ref,supply)<=0:
            raise ValueError('Positive finite asynchronous forcing required')
        return ref,supply

    for i in range(len(z)):
        if comparator_model is not None:
            idle_ref[i],idle_rail[i]=forcing_at((last_time+t[i])/2)
        if idle_step_s is None:
            advance(last_time,float(t[i]-last_time),float(idle_ref[i]),float(idle_rail[i]),last_code)
        else:
            boundaries=np.linspace(last_time,t[i],max(1,math.ceil((t[i]-last_time)/idle_step_s))+1)
            mids=(boundaries[:-1]+boundaries[1:])/2
            refs=np.asarray(reference_at(mids));supplies=np.asarray(rail_at(mids))
            if not np.all(np.isfinite(refs)) or not np.all(np.isfinite(supplies)) or min(refs.min(),supplies.min())<=0:
                raise ValueError('Positive finite idle forcing required')
            for a,stop,ref,supply in zip(boundaries[:-1],boundaries[1:],refs,supplies):
                advance(float(a),float(stop-a),float(ref),float(supply),last_code)
        acquisition_references.append(reference)
        first,last=(start[i],z[i]) if input_control is None else input_control.acquire(i,start[i],z[i],float(t[i]))
        if any(input_test):
            # Ratiometric internal test hypothesis, derived from the retained
            # reservoir, not the ideal external reference forcing. Sampling
            # still uses the same RC, held charge, noise and conversion path.
            fractions={1:0.,2:.25,3:-.25}
            def selected(value):
                parts=[value.real,value.imag]
                for lane,code in enumerate(input_test):
                    if code:parts[lane]=fractions[code]*reference
                return complex(*parts)
            first,last=selected(first),selected(last)
        applied[i]=last
        supply_observations.append((float(t[i]),float(sample_rails[i])))
        acquisition_tau=(p.sample_resistance_ohm+p.diagnostic_series_resistance_ohm)*(p.sample_cap_per_leg_f+p.diagnostic_input_cap_f)*3.3/sample_rails[i]
        decay=math.exp(-p.acquisition_s/acquisition_tau)
        slope=(last-first)/p.acquisition_s
        held=last-slope*acquisition_tau+(held-first+slope*acquisition_tau)*decay
        acq_error.append(abs(held-last))
        # Effective source charge per selected quarter-reference lane. Lump
        # the acquisition demand at its end, before SAR decisions; reference
        # recovery and downstream supply-current replay see the retained droop.
        demand=diagnostic_lanes*p.diagnostic_reference_effective_cap_per_lane_f*reference
        reference-=demand/p.reference_cap_f
        charge_drawn+=demand;diagnostic_charge+=demand;ref_min=min(ref_min,reference)
        observed=held+held_noise[i]+sample_ref[i]/1024*(1+1j)
        accepted_i=accepted_q=0
        cursor=float(t[i])
        for bit,mask in enumerate((512,256,128,64,32,16,8,4,2,1)):
            trial_i=accepted_i+mask;trial_q=accepted_q+mask
            code=complex((trial_i-512)/512,(trial_q-512)/512)
            charge=p.dac_effective_cap_f*(abs(code.real-last_code.real)+abs(code.imag-last_code.imag))*reference
            charge_drawn+=charge;reference-=charge/p.reference_cap_f
            if reference<=0:raise ValueError('Reference reservoir collapsed under trial charge')
            ref_min=min(ref_min,reference)
            if comparator_model is not None:
                targets[i,bit,0],rails[i,bit,0]=forcing_at(cursor+settle[bit]/2)
                bit_start[i,bit]=cursor
            advance(float(bit_start[i,bit]),float(settle[bit]),float(targets[i,bit,0]),float(rails[i,bit,0]),code)
            dac_error=max(dac_error,abs(dac-code*reference))
            decision_references.append(reference)
            decision_observations.append((float(bit_start[i,bit]+settle[bit]),reference))
            margin=observed-dac+comparator_noise[i,bit]
            comparator_margins[i,bit]=margin.real,margin.imag
            if margin.real>0 or (margin.real==0 and trial_i%2==0):accepted_i=trial_i
            if margin.imag>0 or (margin.imag==0 and trial_q%2==0):accepted_q=trial_q
            decision_duration=p.comparator_s
            if comparator_model is not None:
                # Both converters wait for the slower I/Q completion in this
                # explicit lockstep hypothesis; no independent phase refund.
                overdrive=min(abs(margin.real),abs(margin.imag))
                if overdrive==0:raise ValueError('Comparator did not resolve zero overdrive')
                decision_duration=comparator_model['launch_s']+comparator_model['tau_s']*max(
                    0.,math.log(comparator_model['output_threshold_v']/overdrive))
                cursor=float(bit_start[i,bit]+settle[bit]+decision_duration)
                if cursor>t[i]+conversion_s+1e-18:
                    raise ValueError('Asynchronous comparator exceeded total conversion deadline')
                targets[i,bit,1],rails[i,bit,1]=forcing_at(
                    bit_start[i,bit]+settle[bit]+decision_duration/2)
            decision_durations[i,bit]=decision_duration
            advance(float(bit_start[i,bit]+settle[bit]),decision_duration,
                float(targets[i,bit,1]),float(rails[i,bit,1]),code)
            last_code=code
        words[i]=((accepted_i-512)*4,(accepted_q-512)*4)
        last_time=float(t[i]+conversion_s) if comparator_model is None else cursor
        completion_times[i]=last_time
        if input_control is not None:
            input_control.observe(i,complex(words[i,0],words[i,1])/2048,last_time)
    duration=last_time-previous_ends[0]
    source_mean=positive_recharge/duration
    ideal=np.clip(np.rint(np.column_stack((applied.real,applied.imag))/sample_ref[:,None]*512),-512,511)
    error=words/4-ideal
    report=dict(input_test=list(input_test),
        diagnostic_reference_charge_c=diagnostic_charge,
        diagnostic_scope='Ratiometric internal endpoint with optional effective source charge per quarter-reference lane, lumped at acquisition end. Same finite acquisition and retained reference/DAC/comparator path. Zero effective capacitance is an ideal-load control. Continuous source impedance/bias, ratio mismatch and switch injection remain unmodeled. Cannot establish absolute VREF or independent gain accuracy.',
        initial_reference_v=initial_reference,first_acquisition_reference_v=acquisition_references[0],parameters=asdict(p),native_bits=10,transport_bits=12,
        maximum_rate_hz=1/required,schedule_margin_s=period-required,
        conversion_latency_s=conversion_s,
        actual_conversion_latency_interval_s=[float(min(completion_times-t)),float(max(completion_times-t))],
        comparator_model=comparator_model,
        comparator_decision_interval_s=[float(decision_durations.min()),float(decision_durations.max())],
        actual_completion_margin_s=float(conversion_s-max(completion_times-t)),
        timing_ownership="Acquisition timestamps supplied by sample clock; allocated local completion intervals need no further external LO edges. Not a physical sequencer implementation.",
        evaluated_supply_interval_v=[float(min(v for _,v in supply_observations)),float(max(v for _,v in supply_observations))],
        sampling_thermal_rms_per_component_v=thermal,noise_enabled=noise,idle_integration_step_s=idle_step_s,
        code_error_rms_lsb=float(np.sqrt(np.mean(error**2))),maximum_code_error_lsb=float(max(abs(error).ravel())),
        acquisition_error_rms_v=float(np.sqrt(np.mean(np.array(acq_error)**2))),
        reference_interval_v=[ref_min,ref_max],
        decision_reference_interval_v=[float(min(decision_references)),float(max(decision_references))],
        maximum_dac_following_error_at_decision_v=dac_error,
        reference_charge_drawn_c=charge_drawn,signed_reference_recharge_c=signed_recharge,
        reference_charge_balance_residual_c=signed_recharge-charge_drawn-p.reference_cap_f*(reference-initial_reference),
        reference_source_average_a=source_mean,reference_source_peak_a=peak_source,
        reference_with_bias_average_a=source_mean+p.reference_idle_a,
        reference_with_bias_peak_a=peak_source+p.reference_idle_a,
        current_limited_segments=limited_segments,
        scope='Predictive conditional charge/settling/decision recurrence, not fitted silicon. Effective CDAC charge uses absolute code steps and dissipative switching; return-charge reuse and capacitor mismatch are unmodeled. Input acquisition uses linear endpoints; half-LSB midpoint convention is assigned. Optional asynchronous regeneration uses a snapshot input and explicit exponential law; both I/Q wait for the slower decision, DAC settling intervals are preserved, and shared reference forcing is reevaluated at actual event times. Its input snapshot, fixed launch and regeneration law are hypotheses, not physical metastability or sequencer qualification. Fixed-slot mode still assumes timely ideal-sign decisions.')
    final_state=dict(version=1,parameters=json.dumps(asdict(p),sort_keys=True),comparator_model=comparator_identity,end_time_s=last_time,
        held=[held.real,held.imag],reference_v=reference,dac=[dac.real,dac.imag],
        last_code=[last_code.real,last_code.imag],rng_state=rng.bit_generator.state)
    trace=dict(conversion_windows_s=np.c_[t,completion_times],
        comparator_margins_v=comparator_margins,
        decision_reference_observations=np.asarray(decision_observations),
        acquisition_reference_v=np.asarray(acquisition_references),supply_observations=np.asarray(supply_observations),segments=np.asarray(segments),reference_cap_f=p.reference_cap_f,
        reference_limit_a=p.reference_limit_a,mean_source_a=source_mean,final_state=final_state)
    return words,report,trace


def comparator_deadline_screen(margins_v, *, decision_s, launch_s=.1e-9,
                               output_threshold_v=.2, tau_cases_s=(25e-12,50e-12,75e-12,100e-12)):
    """Inverse regenerative-comparator requirement, not a device noise model.

    Vout = Vin * exp((t-launch)/tau), unity initial gain. Margins come from
    the actual SAR DAC/reference/acquisition trajectory including assigned noise.
    A missed deadline invalidates the ideal-sign decision used by that trajectory;
    it is not silently replaced with a correct bit or a measured error rate.
    """
    margins=np.asarray(margins_v,float)
    if margins.ndim!=3 or margins.shape[1:]!=(10,2) or not len(margins) or not np.all(np.isfinite(margins)):
        raise ValueError('Finite conversions by ten decisions by two channels required')
    if not all(math.isfinite(x) for x in (decision_s,launch_s,output_threshold_v)) or not 0<=launch_s<decision_s or output_threshold_v<=0:
        raise ValueError('Positive remaining regeneration interval and threshold required')
    rows=[]
    for tau in tau_cases_s:
        if not math.isfinite(tau) or tau<=0:raise ValueError('Positive finite regeneration time constant required')
        threshold=output_threshold_v*math.exp(-(decision_s-launch_s)/tau)
        misses=np.abs(margins)<threshold
        rows.append(dict(tau_s=tau,minimum_resolvable_input_v=threshold,
            unresolved_decisions=int(misses.sum()),
            conversions_with_unresolved_decision=int(np.any(misses,axis=(1,2)).sum()),
            unresolved_by_bit_msb_first=misses.sum(axis=(0,2)).astype(int).tolist()))
    return dict(decision_s=decision_s,launch_s=launch_s,output_threshold_v=output_threshold_v,
        comparisons=int(margins.size),conversions=len(margins),cases=rows,
        scope='Assigned exponential regeneration, unity input gain and fixed launch delay; '
        'conditional deadline counts on the ideal-sign trajectory, not a metastability probability or corrected ADC simulation. '
        'Input-referred noise is already included; physical regeneration noise, supply dependence, '
        'internal kickback and recovery remain unmodeled. Any unresolved decision prevents this screen '
        'from qualifying the ideal-sign ENOB result for that comparator hypothesis.')


def local_impedance(frequencies,candidate):
    """Local current port: die cap in parallel with supply + return path."""
    f=np.asarray(frequencies,float);s=2j*np.pi*f;n=candidate['network']
    zfeed=n['feed_r']+s*n['feed_l']
    # Capacitor branches are open at DC, avoiding 1/0 intermediates.
    yboard=s*n['board_c']/(1+s*n['board_c']*n['board_esr']+s*s*n['board_c']*n['board_esl'])
    zboard=1/(1/zfeed+yboard)
    zpath=zboard+n['package_r']+s*n['package_l']+candidate['return_r_ohm']+s*candidate['return_l_h']
    ydie=s*n['die_c']/(1+s*n['die_c']*n['die_esr']+s*s*n['die_c']*n['die_esl'])
    return -1/(1/zpath+ydie)


def coupled_reference_load_transfer(frequencies,candidate,*,cap_f=3e-12,
        bond_l_h=2e-9,source_r_ohm=50.2,link_r_ohm=1e-5,differential=None):
    """Local load to rail, return and REF_IN voltage in the tied five-node PDN.

    Exact series/parallel reduction of the baseline return topology: 10% common
    return, equal remaining branches, 20 pF inter-return coupling and the finite
    ground link. No host-side reservoir or isolated-return variant is implied.
    Positive current is drawn from quiet VDD into quiet ground. The independent
    external voltage source is zeroed for this incremental transfer, retaining
    its impedance, bond and receiver capacitance.
    """
    f=np.asarray(frequencies,float)
    if np.any(~np.isfinite(f)) or np.any(f<0):raise ValueError('Finite nonnegative frequencies required')
    if not all(math.isfinite(v) and v>0 for v in (bond_l_h,source_r_ohm,link_r_ohm)) or not math.isfinite(cap_f) or cap_f<0:
        raise ValueError('Passive finite reference-input parameters required')
    s=2j*np.pi*f;n=candidate['network']
    total=candidate['return_r_ohm']+s*candidate['return_l_h']
    arm=1.8*total
    link=1/(1/link_r_ohm+s*20e-12)
    return_z=.1*total+1/(1/arm+1/(arm+link))
    leg_ratio=None
    if differential is None:
        input_ratio=1/(1+s*cap_f*(source_r_ohm+s*bond_l_h))
        input_y=s*cap_f*input_ratio
    else:
        # Zero both external voltage sources, retaining the coupled bonds and
        # each pad capacitance. Solve (I + Z_source * diag(s*C)) Vlocal = -Vg.
        # This form includes DC without infinite capacitor impedances.
        mismatch=differential['mismatch'];opposed=differential['opposed']
        common_gain=differential['cm_gain'];mutual=differential.get('mutual_l_h',.4e-9)
        if (not math.isfinite(mismatch) or abs(mismatch)>=1 or
                not math.isfinite(common_gain) or not math.isfinite(mutual) or
                mutual<0 or mutual>=bond_l_h*math.sqrt(1-mismatch*mismatch)):
            raise ValueError('Finite mismatch, common-mode gain and passive coupled bonds required')
        delta=np.array([1.,-1.])*mismatch
        c=cap_f*(1+delta);l=bond_l_h*(1+(-delta if opposed else delta));r=source_r_ohm*(1+delta/2)
        a=1+s*c[0]*(r[0]+s*l[0]);d=1+s*c[1]*(r[1]+s*l[1])
        b=s*s*mutual*c[1];q=s*s*mutual*c[0];det=a*d-b*q
        leg_ratio=np.stack(((d-b)/det,(a-q)/det),axis=-1)
        input_y=s*np.sum(leg_ratio*c,axis=-1)
        input_ratio=leg_ratio[...,0]-leg_ratio[...,1]+common_gain*np.mean(leg_ratio,axis=-1)
    loaded_return=1/(1/return_z+input_y)
    board_y=s*n['board_c']/(1+s*n['board_c']*n['board_esr']+s*s*n['board_c']*n['board_esl'])
    board_z=1/(1/(n['feed_r']+s*n['feed_l'])+board_y)
    path=board_z+n['package_r']+s*n['package_l']+loaded_return
    die_y=s*n['die_c']/(1+s*n['die_c']*n['die_esr']+s*s*n['die_c']*n['die_esl'])
    rail=-1/(1/path+die_y)
    ground=-rail/path*loaded_return
    result=dict(rail_v_per_a=rail,return_v_per_a=ground,
        input_v_per_a=-input_ratio*ground)
    if leg_ratio is not None:result['input_leg_v_per_a']=-leg_ratio*ground[...,None]
    return result


def supply_delay_gain(sensitivity_ps_per_mv=.1, sign=1.):
    """Convert an explicit nonnegative magnitude and sign to seconds/volt."""
    if sign not in (-1.,1.):raise ValueError('Explicit supply-delay sensitivity sign required')
    if not math.isfinite(sensitivity_ps_per_mv) or sensitivity_ps_per_mv<0:
        raise ValueError('Finite nonnegative supply-delay sensitivity required')
    return sign*sensitivity_ps_per_mv*1e-9


def load_response(trace,candidate,*,grid_s=.25e-9,supply_current_tau_s=.2e-9,reference_input=None,supply_sign=1.,sensitivity_ps_per_mv=.1,dc_reference_a=None,reference_supply_parameters=None,delay_pole_hz=1e9,method="guarded_fft"):
    """Reference source current -> same PDN -> rail, clock-delay, reference.

    AC overlay retains the conservative full planning DC load. Its extra DC
    stress relative to the predicted reference draw is explicitly reported;
    no additional mean reference current is charged on top of the 40 mA owner.
    """
    reference_parameters=({'supply_fraction_per_v':.1,'supply_pole_hz':10e6}
        if reference_supply_parameters is None else reference_supply_parameters)
    reference_gain=reference_parameters['supply_fraction_per_v']
    reference_pole=reference_parameters['supply_pole_hz']
    delay_gain=supply_delay_gain(sensitivity_ps_per_mv,supply_sign)
    segments=trace['segments'];starts=segments[:,0];ends=starts+segments[:,1]
    c=trace['reference_cap_f'];limit=trace['reference_limit_a']
    if dc_reference_a is not None and (not math.isfinite(dc_reference_a) or not 0<=dc_reference_a<=limit):
        raise ValueError('Fixed reference-current allocation must fit the recharge limit')
    # Anchor the grid to absolute time, not the first perturbed ADC timestamp.
    # Otherwise tiny clock changes can move a comparison point outside the
    # prior trace and masquerade as a large unconverged endpoint disturbance.
    beginning=math.floor(min(0.,float(starts[0]))/grid_s)*grid_s
    stop=float(ends[-1]);count=math.ceil((stop-beginning)/grid_s)
    boundaries=beginning+np.arange(count+1)*grid_s
    index=np.clip(np.searchsorted(starts,boundaries,side='right')-1,0,len(starts)-1)
    elapsed=np.clip(boundaries-starts[index],0,segments[index,1])
    initial,target,r=segments[index,2],segments[index,3],segments[index,4]
    error=target-initial;direction=np.sign(error)
    ramp=np.minimum(elapsed,np.maximum(0,(abs(error)-limit*r)*c/limit))
    middle=initial+direction*limit/c*ramp
    value=target+(middle-target)*np.exp(-(elapsed-ramp)/(r*c))
    cumulative=np.r_[0.,np.cumsum(np.maximum(0,segments[:,5]))]
    supplied=cumulative[index]+np.maximum(0,c*(value-initial))
    current=np.diff(supplied)/grid_s
    mean=float(np.mean(current))
    if method not in ('guarded_fft','native_modal'):
        raise ValueError('Unknown reference recharge propagation method')
    if method=='native_modal':
        if dc_reference_a is None or reference_input is None or 'differential' not in reference_input:
            raise ValueError('Causal recharge requires fixed current reservation and differential package')
        if supply_current_tau_s!=.2e-9:
            raise ValueError('Native recharge requires the selected 200ps current pole')
        environment=dict(network=candidate,reference_load_parameters=reference_input,
            reference_supply_parameters=reference_parameters,
            clock_input_configuration=dict(supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
                supply_delay_pole_hz=delay_pole_hz),local_supply_delay_sign=supply_sign)
        result,report=sampled_load_response(boundaries[:-1],current,environment,
            grid_s=grid_s,guard_s=2e-6,method='native_modal')
        poles,fields,_=native_load_modes(environment)
        background={}
        for field,(direct,residues) in fields.items():
            observer_poles=poles
            if len(residues)>len(poles):
                observer_poles=np.r_[poles,-2*np.pi*(delay_pole_hz if field=='delay_s' else reference_pole)]
            background[field]=float(np.real(direct-np.sum(residues/observer_poles))*(-dc_reference_a))
            result[field]+=background[field]
        result['background']=background
        report.update(rail_interval_v=[float(result['rail_v'].min()),float(result['rail_v'].max())],
            mean_reference_current_a=mean,fixed_reference_reserve_a=dc_reference_a,
            current_accounting='fixed_reserved_current_replaced_by_actual_recharge',
            source_charge_c=float(sum(current)*grid_s),
            scope='Causal held-current modal propagation with settled reserved-current background. '
                'Charge-preserving grid averages; samples in a boundary-straddling cell remain grid approximations. '
                'No periodic FFT wraparound. Coupled converter iteration and physical model remain separately qualified.')
        return result,report
    # Two-microsecond guards suppress periodic wrap; report guard comparison in
    # tests rather than treating a periodic FFT as an unqualified transient.
    guard=math.ceil(2e-6/grid_s);size=2**math.ceil(math.log2(len(current)+2*guard))
    if dc_reference_a is None:
        stimulus=np.zeros(size);stimulus[guard:guard+len(current)]=current-mean
    else:
        # Planning DC already reserves this current. Actual recharge replaces
        # it; quiet prehistory/tail draw zero incremental recharge, not a
        # capture-dependent average. Constant background sets the correct
        # settled initial network state through the DC transfer function.
        stimulus=np.full(size,-dc_reference_a)
        stimulus[guard:guard+len(current)]+=current
    frequency=np.fft.rfftfreq(size,grid_s);spectrum=np.fft.rfft(stimulus)
    drive=spectrum/(1+2j*np.pi*frequency*supply_current_tau_s)
    coupled=None if reference_input is None else coupled_reference_load_transfer(frequency,candidate,**reference_input)
    response=drive*(local_impedance(frequency,candidate) if coupled is None else coupled['rail_v_per_a'])
    # Retain the physical relaxation tail rather than hard-resetting the rail
    # and clock perturbation at the final ADC code. A later TX queries this same
    # absolute-time trajectory, including the quiet interval before launch.
    end=guard+len(current)+guard
    rail=np.fft.irfft(response,n=size)[guard:end]
    delay=np.fft.irfft(response*delay_gain/(1+1j*frequency/delay_pole_hz),n=size)[guard:end]
    reference=np.fft.irfft(response*reference_gain/(1+1j*frequency/reference_pole),n=size)[guard:end]
    times=beginning+(np.arange(len(rail))+.5)*grid_s
    result=dict(times_s=times,rail_v=rail,delay_s=delay,reference_fraction=reference,
        resolved_offset_hz=.5/grid_s)
    if coupled is not None:
        result['input_v']=np.fft.irfft(drive*coupled['input_v_per_a'],n=size)[guard:end]
        result['return_v']=np.fft.irfft(drive*coupled['return_v_per_a'],n=size)[guard:end]
        if 'input_leg_v_per_a' in coupled:
            result['input_leg_v']=np.fft.irfft(drive[:,None]*coupled['input_leg_v_per_a'],n=size,axis=0)[guard:end]
    background_current=0. if dc_reference_a is None else -dc_reference_a
    dc_rail=(local_impedance(np.array([0.]),candidate)[0] if coupled is None else coupled['rail_v_per_a'][0]).real*background_current
    background=dict(rail_v=float(dc_rail),delay_s=float(dc_rail*delay_gain),reference_fraction=float(dc_rail*reference_gain))
    if coupled is not None:
        for field in ('input_v','return_v','input_leg_v'):
            if field+'_per_a' in coupled:
                background[field]=np.asarray(coupled[field+'_per_a'][0].real*background_current).tolist()
    result['background']=background
    tail_residual={field:np.asarray(result[field][-1]-value).tolist() for field,value in background.items()}
    report=dict(grid_s=grid_s,supply_current_tau_s=supply_current_tau_s,
        coupled_reference_input=reference_input,supply_sensitivity_sign=supply_sign,supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        direct_input_voltage_in_timing=False,
        dc_reference_a=dc_reference_a,settled_quiet_background=background,final_guard_residual=tail_residual,
        current_accounting='legacy_capture_mean_centered' if dc_reference_a is None else 'fixed_reserved_current_replaced_by_actual_recharge',
        sampled_source_average_a=mean,integrated_source_charge_c=float(sum(current)*grid_s),
        charge_resampling_residual_c=float(sum(current)*grid_s-cumulative[-1]),
        rail_interval_v=[float(min(rail)),float(max(rail))],rail_rms_v=float(np.sqrt(np.mean(rail**2))),
        clock_delay_rms_s=float(np.sqrt(np.mean(delay**2))),
        reference_fraction_rms=float(np.sqrt(np.mean(reference**2))),
        scope='Local reference recharge port only, superposed with host ripple at full planning DC. Positive source charge is conserved; sink current receives no supply-energy credit. Assigned 200 ps supply-current pole requires an internal charge path; not a validated buffer. FFT guards, finite grid and linear fixed PDN do not qualify physical peak current or broadband transistor noise.')
    if dc_reference_a is None:
        report['scope']+=' Legacy mean centering depends on the complete capture; it is not a causal DC allocation for lifecycle use.'
    else:
        report['scope']+=' Fixed reserved current is replaced by recharge; zero-recharge prehistory/tail and settled DC background are explicit assumptions. FFT response remains a finite guarded approximation.'
    if coupled is not None:
        report.update(input_voltage_abs_peak_v=float(max(abs(result['input_v']))),
            input_voltage_rms_v=float(np.sqrt(np.mean(result['input_v']**2))),
            return_voltage_abs_peak_v=float(max(abs(result['return_v']))),
            scope=report['scope']+' Coupled tied-return REF_IN voltage is exposed; the delivered-clock consumer must separately solve perturbed threshold events.')
    if 'input_leg_v' in result:
        report['input_leg_voltage_abs_peak_v']=np.max(abs(result['input_leg_v']),axis=0).tolist()
    return result,report


def reference_load_parameters(environment):
    from reference_input_probe import reference_passive_parameters
    parameters=dict(environment.get('reference_load_parameters',{}))
    shared=reference_passive_parameters(environment)
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    for key in ('cap_f','bond_l_h','source_r_ohm'):
        if bound and parameters.get(key,shared[key])!=shared[key]:
            raise ValueError('Reference load capacitance conflicts with shared pad' if key=='cap_f' else 'Reference load conflicts with shared package: '+key)
        parameters.setdefault(key,shared[key])
    if 'differential' in parameters:
        differential=dict(parameters['differential'])
        if bound and differential.get('mutual_l_h',shared['mutual_l_h'])!=shared['mutual_l_h']:
            raise ValueError('Reference load conflicts with shared package: mutual_l_h')
        differential.setdefault('mutual_l_h',shared['mutual_l_h'])
        parameters['differential']=differential
    return parameters


def native_load_modes(environment):
    """Finite descriptor modes plus algebraic feedthrough, current pole included."""
    from scipy.linalg import eig
    from selected_rf import reference_supply_parameters,clock_supply_delay_pole,clock_supply_sensitivity
    reference=reference_supply_parameters(environment)
    from reference_input_probe import package_descriptor
    params=reference_load_parameters(environment);opts=params.get('differential')
    if opts is None:raise ValueError('Native modal load requires the differential package model')
    defaults=dict(cap_f=3e-12,bond_l_h=2e-9,source_r_ohm=50.2,link_r_ohm=1e-5)
    if any(k not in ('differential','cap_f','bond_l_h','source_r_ohm') and (k not in defaults or v!=defaults[k]) for k,v in params.items()):
        raise ValueError('Native descriptor supports the selected input topology only')
    E,G,F=package_descriptor(environment['network'],mismatch=opts['mismatch'],opposed=opts['opposed'],cap_f=params['cap_f'],bond_l_h=params['bond_l_h'],
        source_r_ohm=params['source_r_ohm'],mutual_l_h=opts['mutual_l_h'])
    values,left,right=eig(-G,E/1e-9,left=True,right=True,homogeneous_eigvals=True)
    finite=abs(values[1])>1e-10*np.maximum(abs(values[0]),abs(values[1]))
    poles=values[0,finite]/values[1,finite]/1e-9;left=left[:,finite];right=right[:,finite]
    if len(poles)!=10 or np.any(poles.real>=0):raise ValueError('Unresolved passive descriptor modes')
    drive=F@np.array([0.,-1.,0.,1.,0.,0.,0.])
    C=np.zeros((3,len(E)));C[0,1]=1.;C[0,3]=-1.;C[2,3]=1.
    C[1,5]=1+opts['cm_gain']/2;C[1,6]=-1+opts['cm_gain']/2;C[1,3]=-opts['cm_gain']
    residues=(C@right)*(left.conj().T@drive)/np.diag(left.conj().T@E@right)
    def exact(s):return C@np.linalg.solve(G+s*E,drive)
    def finite_part(s):return np.sum(residues/(s-poles),axis=1)
    d0=exact(0.)-finite_part(0.);d1=(exact(1e10)-finite_part(1e10)-d0)/1e10
    errors=[float(np.max(abs(exact(2j*np.pi*f)-(d0+d1*2j*np.pi*f+finite_part(2j*np.pi*f))))) for f in np.geomspace(1e3,1e11,41)]
    if max(errors)>1e-6:raise ValueError('Descriptor modal transfer reconstruction failed')
    omega=1/.2e-9
    current_residues=residues*omega/(poles+omega)
    direct=d1*omega
    current_residues=np.column_stack((current_residues,d0*omega-d1*omega**2-np.sum(current_residues,axis=1)))
    poles=np.r_[poles,-omega]
    fields={name:(direct[k],current_residues[k]) for k,name in enumerate(('rail_v','input_v','return_v'))}
    for name,scale,cutoff in [('delay_s',supply_delay_gain(clock_supply_sensitivity(environment),environment.get('local_supply_delay_sign',1.)),clock_supply_delay_pole(environment)),('reference_fraction',reference['supply_fraction_per_v'],reference['supply_pole_hz'])]:
        w=2*np.pi*cutoff;d,r=fields['rail_v'];filtered=r*w/(poles+w)
        fields[name]=(0.,np.r_[scale*filtered,scale*(d*w-sum(filtered))])
    return poles,fields,max(errors)


def sampled_load_response(times_s,current_a,environment,*,grid_s=1e-9,guard_s=2e-6,method='auto',initial_state=None):
    """Preserve native current samples through exact held-input modal propagation.

    Requested coarse grids never discard current before the network. Output is
    retained at native sample midpoints; downstream interpolation remains finite.
    """
    if method not in ('auto','native_modal','coarse_fft'):raise ValueError('Unknown current propagation method')
    paired='differential' in environment.get('reference_load_parameters',{})
    if method=='coarse_fft' or (method=='auto' and not paired):
        if initial_state is not None:raise ValueError('State continuation requires native modal propagation')
        return _sampled_load_response_fft(times_s,current_a,environment,grid_s=grid_s,guard_s=guard_s)
    from scipy.signal import lfilter
    t=np.asarray(times_s,float);current=np.asarray(current_a,float)
    if (t.ndim!=1 or len(t)<2 or current.shape!=t.shape or not np.all(np.isfinite(t)) or not np.all(np.isfinite(current)) or
            not math.isfinite(grid_s) or grid_s<=0 or not math.isfinite(guard_s) or guard_s<=0):
        raise ValueError('Finite uniform current trajectory and positive grid/tail required')
    step=float((t[-1]-t[0])/(len(t)-1))
    if step<=0 or not np.allclose(np.diff(t),step,rtol=1e-7,atol=1e-18):raise ValueError('Uniform increasing current sample times required')
    poles,fields,error=native_load_modes(environment)
    # Every output observes the same source-driven modes. Calculate each mode
    # once, including the two filtered observers, rather than once per field.
    from selected_rf import reference_supply_parameters,clock_supply_delay_pole,clock_supply_sensitivity
    reference=reference_supply_parameters(environment)
    all_poles=np.r_[poles,-2*np.pi*clock_supply_delay_pole(environment),-2*np.pi*reference['supply_pole_hz']]
    signature=json.dumps(dict(clock_delay_pole_hz=clock_supply_delay_pole(environment),reference_supply=reference,network=environment['network'],input=reference_load_parameters(environment),
        sensitivity=clock_supply_sensitivity(environment),sign=environment.get('local_supply_delay_sign',1.)),sort_keys=True)
    initial=np.zeros(len(all_poles),complex);gap=0.
    if initial_state is not None:
        if initial_state.get('version')!=1 or initial_state.get('signature')!=signature:
            raise ValueError('Native load state does not match the network/observers')
        saved_poles=np.asarray(initial_state['poles_s'],float);saved=np.asarray(initial_state['modes'],float)
        if saved.shape!=(len(all_poles),2) or saved_poles.shape!=saved.shape or not np.all(np.isfinite(saved)) or not np.all(np.isfinite(saved_poles)):
            raise ValueError('Finite matching native modal state required')
        if not np.allclose(saved_poles[:,0]+1j*saved_poles[:,1],all_poles,rtol=1e-10,atol=1e-6):
            raise ValueError('Native modal basis changed')
        previous_time=float(initial_state['time_s'])
        if not math.isfinite(previous_time):raise ValueError('Finite state time required')
        gap=float(t[0]-previous_time)
        tolerance=4*max(abs(np.spacing(t[0])),abs(np.spacing(previous_time)))
        if gap < -tolerance:raise ValueError('Native load continuation overlaps committed input')
        gap=max(0.,gap);initial=(saved[:,0]+1j*saved[:,1])*np.exp(all_poles*gap)
    forcing=np.r_[current,np.zeros(math.ceil(guard_s/step))]
    result={name:np.real(direct)*forcing.copy() for name,(direct,_) in fields.items()}
    coefficients={}
    for name,(_,residues) in fields.items():
        vector=np.zeros(len(all_poles),complex);vector[:len(poles)]=residues[:len(poles)]
        if len(residues)>len(poles):vector[-2 if name=='delay_s' else -1]=residues[-1]
        coefficients[name]=vector
    final=np.zeros_like(initial)
    for k,pole in enumerate(all_poles):
        a=np.exp(pole*step);integral=np.expm1(pole*step)/pole
        end,_=lfilter([integral],[1.,-a],forcing,zi=np.array([a*initial[k]]))
        start=np.r_[initial[k],end[:-1]]
        midpoint=np.exp(pole*step/2)*start+np.expm1(pole*step/2)/pole*forcing
        for name,vector in coefficients.items():
            if vector[k]!=0:result[name]+=np.real(vector[k]*midpoint)
        final[k]=end[len(current)-1]
    final_state=dict(version=1,signature=signature,time_s=float(t[0]+len(current)*step),
        poles_s=np.column_stack((all_poles.real,all_poles.imag)).tolist(),
        modes=np.column_stack((final.real,final.imag)).tolist())
    result['final_state']=final_state
    # Native sample Nyquist is an observation limit, not an added tone at
    # that frequency. Consumers must preserve this grid separately from the
    # explicitly retained source/rail forcing-frequency check.
    result.update(times_s=t[0]+(np.arange(len(forcing))+.5)*step,
        background={k:0. for k in fields},resolved_offset_hz=0.,native_source_step_s=step)
    report=dict(method='native_modal_zoh',grid_s=step,requested_grid_s=grid_s,quiet_tail_s=guard_s,
        initial_state='zero_incremental' if initial_state is None else 'continued',quiet_gap_s=gap,
        committed_input_end_s=final_state['time_s'],
        current_interval_a=[float(current.min()),float(current.max())],integrated_charge_c=float(sum(current)*step),
        resampling_charge_error_c=0.,modal_transfer_maximum_error_ohm=error,
        rail_interval_v=[float(result['rail_v'].min()),float(result['rail_v'].max())],
        final_guard_residual={k:float(result[k][-1]) for k in fields},
        scope='Exact held-input recurrence of selected linear descriptor modes and assigned 200ps current pole, with explicit zero or continued incremental initial state and retained natural tail. final_state commits only supplied input, not extrapolated quiet tail; an omitted gap explicitly means zero incremental current. Native current samples are not coarsened. Output midpoint interpolation, source waveform sampling, modal floating-point accuracy and physical current law remain uncertainties; requested_grid_s is diagnostic metadata, not an independent output resolution.')
    return result,report


def _sampled_load_response_fft(times_s,current_a,environment,*,grid_s=1e-9,guard_s=2e-6):
    """Charge-preserving sampled local-load perturbation, zero settled background.

    Samples specify piecewise-constant current over the following source step.
    This models an assigned envelope current, not RF-cycle switching current.
    """
    t=np.asarray(times_s,float);current=np.asarray(current_a,float)
    if (t.ndim!=1 or len(t)<2 or current.shape!=t.shape or
            not np.all(np.isfinite(t)) or not np.all(np.isfinite(current)) or
            not math.isfinite(grid_s) or grid_s<=0 or not math.isfinite(guard_s) or guard_s<=0):
        raise ValueError('Finite uniform current trajectory and positive grid/guard required')
    step=float(t[1]-t[0])
    if step<=0 or not np.allclose(np.diff(t),step,rtol=1e-7,atol=1e-18):
        raise ValueError('Uniform increasing current sample times required')
    edges=t[0]+np.arange(len(t)+1)*step
    cumulative=np.r_[0.,np.cumsum(current)*step]
    count=math.ceil((edges[-1]-edges[0])/grid_s)
    boundaries=t[0]+np.arange(count+1)*grid_s
    charge=np.interp(boundaries,edges,cumulative,left=0.,right=cumulative[-1])
    sampled=np.diff(charge)/grid_s
    guard=math.ceil(guard_s/grid_s);size=2**math.ceil(math.log2(count+2*guard))
    stimulus=np.zeros(size);stimulus[guard:guard+count]=sampled
    frequency=np.fft.rfftfreq(size,grid_s)
    drive=np.fft.rfft(stimulus)/(1+2j*np.pi*frequency*.2e-9)
    ports=coupled_reference_load_transfer(frequency,environment['network'],**reference_load_parameters(environment))
    from selected_rf import reference_supply_transfer,clock_supply_delay_pole,clock_supply_sensitivity
    gain=supply_delay_gain(clock_supply_sensitivity(environment),environment.get('local_supply_delay_sign',1.))
    transfer=dict(rail_v=ports['rail_v_per_a'],input_v=ports['input_v_per_a'],return_v=ports['return_v_per_a'],
        delay_s=ports['rail_v_per_a']*gain/(1+1j*frequency/clock_supply_delay_pole(environment)),
        reference_fraction=ports['rail_v_per_a']*reference_supply_transfer(environment,frequency))
    result={k:np.fft.irfft(drive*v,n=size)[:count+2*guard] for k,v in transfer.items()}
    result.update(times_s=t[0]+(np.arange(count+2*guard)-guard+.5)*grid_s,
        background={k:0. for k in transfer},resolved_offset_hz=.5/grid_s)
    report=dict(grid_s=grid_s,guard_s=guard_s,current_interval_a=[float(current.min()),float(current.max())],
        integrated_charge_c=float(cumulative[-1]),resampling_charge_error_c=float(sum(sampled)*grid_s-cumulative[-1]),
        rail_interval_v=[float(result['rail_v'].min()),float(result['rail_v'].max())],
        final_guard_residual={k:float(result[k][-1]) for k in transfer},
        scope='Assigned piecewise-constant envelope supply-current perturbation, charge-preserving bin averages, 200 ps current pole, tied-return linear PDN and guarded FFT. Absolute time retained. Finite grid/guard approximation; not RF-cycle supply current, physical driver law or causal state-space proof.')
    return result,report


def sum_load_responses(first,second):
    """Superpose linear local-load responses on their finest absolute grid."""
    if first is None:return second
    step=min(float(np.min(np.diff(x['times_s']))) for x in (first,second))
    start=min(x['times_s'][0] for x in (first,second));stop=max(x['times_s'][-1] for x in (first,second))
    times=start+np.arange(math.ceil((stop-start)/step)+1)*step
    fields=('rail_v','delay_s','reference_fraction','input_v','return_v')
    result=dict(times_s=times,background={},resolved_offset_hz=max(first['resolved_offset_hz'],second['resolved_offset_hz']))
    native_steps=[r['native_source_step_s'] for r in (first,second) if 'native_source_step_s' in r]
    if native_steps:result['native_source_step_s']=min(native_steps)
    for field in fields:
        if field not in first and field not in second:continue
        result[field]=np.zeros_like(times);background=0.
        for response in (first,second):
            if field not in response:continue
            quiet=response.get('background',{}).get(field,0.);background+=quiet
            result[field]+=np.interp(times,response['times_s'],response[field],left=quiet,right=quiet)
        result['background'][field]=background
    return result


def feedback_change(updated,previous):
    """Numerical fixed-point check at every exposed analog feedback boundary."""
    if previous is None:return dict(converged=False,fields={})
    common=(updated['times_s']>=previous['times_s'][0])&(updated['times_s']<=previous['times_s'][-1])
    if not np.any(common):raise ValueError('Feedback trajectories must overlap')
    limits={'rail_v':20e-6,'input_v':1e-6,'return_v':1e-6,'reference_fraction':1e-6,'delay_s':1e-15}
    fields={}
    for field,limit in limits.items():
        if field not in updated and field not in previous:continue
        if field not in updated or field not in previous:raise ValueError('Feedback fields changed between iterations')
        difference=updated[field][common]-np.interp(updated['times_s'][common],previous['times_s'],previous[field])
        rms=float(np.sqrt(np.mean(difference**2)));peak=float(np.max(abs(difference)))
        fields[field]=dict(rms_change=rms,peak_change=peak,peak_limit=limit,
            within_limit=bool(peak<=limit and (field!='rail_v' or rms<=1e-6)))
    return dict(converged=bool(fields) and all(x['within_limit'] for x in fields.values()),fields=fields,
        scope='Numerical trajectory agreement on common capture only; tolerances are solver controls, not silicon-performance specifications.')


def response_change(updated,previous):
    if previous is None:return None,None,False
    # Compare the common physical capture, without extrapolating a terminal
    # value across an infinitesimal change of the capture endpoint.
    common=(updated['times_s']>=previous['times_s'][0]) & (updated['times_s']<=previous['times_s'][-1])
    prior=np.interp(updated['times_s'][common],previous['times_s'],previous['rail_v'])
    difference=updated['rail_v'][common]-prior
    rms=float(np.sqrt(np.mean(difference**2)));peak=float(max(abs(difference)))
    return rms,peak,rms<=1e-6 and peak<=20e-6


def tone_precision(environment,parameters,*,bin_number=499,count=2048,amplitude=.65,
                   shared_clock_feedback=False,comparator_model=None):
    """Converter precision at substantial swing, with its own PDN feedback.

    A fitted sine/cosine/DC removes gain, phase and offset only. Residual includes
    nonlinear distortion, noise and jitter. This is not a waveform equalizer.
    """
    validate_sar_binding(environment,parameters,comparator_model=comparator_model)
    if shared_clock_feedback and (any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))):
        required=['local_supply_delay_sign','local_supply_sensitivity_ps_per_mv']
        if 'periodic_clock' in environment:required.append('reference_load_parameters')
        missing=[key for key in required if key not in environment]
        if missing:raise ValueError('Design-bound converter clock feedback missing '+', '.join(missing))
    from selected_rf import DeliveredClock,reference_at,rail_at,reference_supply_parameters,clock_supply_delay_pole,clock_supply_sensitivity
    config=environment.get('resolved_configuration')
    if config is not None and (config['engine']!='rf' or config['direction']!='rx'):
        raise ValueError('Converter tone requires an RF receive configuration')
    fs=config['sample_hz'] if config is not None else environment['carrier_hz']/64
    frequency=fs*bin_number/count
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        noise=environment.get('adc_noise_parameters')
        if not isinstance(noise,dict) or 'aperture_rms_s' not in noise:
            raise ValueError('Design-bound converter tone requires ADC aperture parameters')
        aperture_rms=noise['aperture_rms_s']
    else:
        aperture_rms=10e-12  # Independent converter fixture.
    if isinstance(aperture_rms,bool) or not isinstance(aperture_rms,(int,float)) or not math.isfinite(aperture_rms) or aperture_rms<0:
        raise ValueError('Finite nonnegative ADC aperture jitter required')
    from selected_rf import validate_rf_configuration_identity
    validate_rf_configuration_identity(environment)
    targets=None
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        receiver=environment.get('receiver_parameters')
        if not isinstance(receiver,dict) or any(
                not isinstance(receiver.get(name),dict) or 'enob_target' not in receiver[name]
                for name in ('adc_i','adc_q')):
            raise ValueError('Design-bound converter tone requires paired ENOB targets')
        targets=[receiver[name]['enob_target'] for name in ('adc_i','adc_q')]
        if any(isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0 for value in targets):
            raise ValueError('Positive finite converter ENOB targets required')
    context=deepcopy(dict(design_provenance=environment.get('design_provenance'),
        resolved_configuration=config,scenario_overrides=environment.get('scenario_overrides',[]),
        scenario_assumptions=environment.get('scenario_assumptions',{})))
    ideal=(np.arange(count)+1)/fs
    aperture=np.random.default_rng(411).normal(0,aperture_rms,count)
    response=None;history=[];converged=False
    for iteration in range(4):
        e=environment if response is None else dict(environment,local_load_response=response)
        actual=ideal+DeliveredClock(e).crossing_error(ideal,e['carrier_hz'])+aperture
        values=amplitude*np.exp(2j*np.pi*frequency*actual)
        starts=amplitude*np.exp(2j*np.pi*frequency*(actual-parameters.acquisition_s))
        words,converter,trace=paired_sar(values,starts,actual,
            lambda t:reference_at(e,t),lambda t:rail_at(e,t),parameters=parameters,comparator_model=comparator_model)
        options={}
        if shared_clock_feedback:
            options=dict(reference_input=reference_load_parameters(e)
                         if 'periodic_clock' in e else None,
                         supply_sign=e.get('local_supply_delay_sign',1.),
                         sensitivity_ps_per_mv=clock_supply_sensitivity(e),
                         dc_reference_a=trace['reference_limit_a'])
        options.update(reference_supply_parameters=reference_supply_parameters(e),delay_pole_hz=clock_supply_delay_pole(e))
        options.setdefault('sensitivity_ps_per_mv',clock_supply_sensitivity(e))
        updated,load=load_response(trace,e['network'],**options)
        rms,peak,converged=response_change(updated,response)
        history.append(dict(iteration=iteration,rail_rms_change_v=rms,rail_maximum_change_v=peak))
        response=updated
        if converged:break
    # Exclude startup and terminal guards from the precision measurement.
    basis=np.column_stack((np.cos(2*np.pi*frequency*ideal),np.sin(2*np.pi*frequency*ideal),np.ones(count)))[128:-128]
    observed=words[128:-128]/2048
    coefficients=np.linalg.lstsq(basis,observed,rcond=None)[0]
    fitted=basis@coefficients
    residual=np.sqrt(np.mean((observed-fitted)**2,axis=0))
    fitted_peak=np.sqrt(np.sum(coefficients[:2]**2,axis=0))
    sinad=20*np.log10(fitted_peak/(math.sqrt(2)*residual))
    # Full-scale 2 Vpp ideal quantizer RMS = 2 / (sqrt(12)*2**bits).
    enob=np.log2(2/(math.sqrt(12)*residual))
    return dict(**context,
        aperture_rms_s=aperture_rms,frequency_hz=frequency,sample_hz=fs,input_peak_per_component_v=amplitude,
        measured_samples_per_component=len(observed),residual_rms_v=residual.tolist(),
        sinad_db=sinad.tolist(),fullscale_normalized_enob=enob.tolist(),
        fitted_peak_v=fitted_peak.tolist(),fitted_offset_v=coefficients[2].tolist(),
        design_enob_targets=targets,meets_design_enob_target=None if targets is None else bool(np.all(enob>=targets)),
        meets_assigned_8enob=bool(min(enob)>=8),fixed_8enob_comparison_scope='Independent fixed benchmark; design acceptance uses design_enob_targets',
        numerical_feedback_converged=converged,
        iterations=history,converter=converter,load_response=load,
        comparator_deadlines=comparator_deadline_screen(trace['comparator_margins_v'],decision_s=parameters.comparator_s),
        comparator_deadline_interpretation='Fixed-slot counterfactual only; asynchronous completion uses the total conversion budget' if comparator_model is not None else 'Actual fixed-slot allocation requirement',
        minimum_sampled_rail_v=float(min(rail_at(e,actual))),
        scope='Known sine characterization, not protocol training. I and Q are tested together against their shared reference. Full-scale-normalized ENOB includes residual harmonic distortion and noise after fitting only a fundamental and DC. This stimulus has its own reference-current/PDN feedback; it does not borrow an OFDM load trajectory. Assigned noise, poles, midpoint-held supply sensitivity and comparator interval still need physical evidence.')
