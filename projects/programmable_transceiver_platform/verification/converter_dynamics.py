"""Closed-loop paired SAR requirement model and its shared-supply load.

Not identified GF180 devices: every pole, capacitor, current and noise value is
an explicit hypothesis. Comparator decisions generate subsequent trial codes
and reference charge; measured code/reference histories are never inputs.
"""
from dataclasses import dataclass, asdict
import math
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


class ObservedGain:
    """Code-only FPGA gain policy plus causal command/PGA settling dynamics.

    Physical timestamps schedule propagation; the policy sees only completed
    ADC words. No source bits, packet boundary, wanted power or true gain target
    are available to its decisions. Analogue clipping uses supplied rail bounds.
    """
    def __init__(self,*,sample_hz,command_latency_s,acquisition_s,
                 headroom_start,headroom_end,initial_gain_db=40.,maximum_gain_db=60.):
        if not 0<=initial_gain_db<=maximum_gain_db or command_latency_s<0:
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
            self.gain=10**(self.target_db/20)+(self.gain-10**(self.target_db/20))*math.exp(-(when-self.time)/.2e-6)
            self.time=when;self.target_db=target;self.pending=None;self.updates+=1
        target=10**(self.target_db/20)
        self.gain=target+(self.gain-target)*math.exp(-(time-self.time)/.2e-6)
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
                target=float(np.clip(self.target_db+correction,0.,self.maximum_gain_db))
                apply_s=available_s+self.command_latency_s
                self.pending=(apply_s,target)
                self.commands.append(dict(last_observed_code=index,code_available_s=available_s,
                    earliest_apply_s=apply_s,target_gain_db=target))

    def report(self):
        return dict(gain_db=self.trace,pga_clipped_samples=self.clipped,applied_updates=self.updates,
            command_latency_s=self.command_latency_s,initial_gain_db=self.initial_gain_db,
            maximum_gain_db=self.maximum_gain_db,converter_bits=10,transport_bits=12,
            native_transport_low_two_bits_zero=True,commands=self.commands,
            scope='Completed native SAR codes drive bounded FPGA gain commands. Service delay begins after conversion availability; target changes propagate through a 0.2 us PGA pole. Instantaneous rail limits affect physical clipping, not the FPGA policy.')


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


def paired_sar(values, starts, sample_times, reference_at, rail_at, *,
               parameters=SARParameters(), noise=True, seed=4901, input_control=None):
    """Sample/hold plus ten decisions, with one shared I/Q reference reservoir.

    Input endpoints describe a linear acquisition-window trajectory. Sample
    capacitors retain their preceding held input. Reference and DAC states
    persist across all bits and conversions. Reference source and DAC pole
    resistance scale as 3.3/local_rail: an assigned supply sensitivity.
    """
    p=parameters;z=np.asarray(values,complex);start=np.asarray(starts,complex);t=np.asarray(sample_times,float)
    if (z.ndim!=1 or not len(z) or start.shape!=z.shape or t.shape!=z.shape or
            not np.all(np.isfinite(z)) or not np.all(np.isfinite(start)) or
            not np.all(np.isfinite(t)) or np.any(np.diff(t)<=0)):
        raise ValueError('Finite acquisition endpoints and increasing sampling times required')
    if (not all(math.isfinite(v) for k,v in asdict(p).items() if k!='bit_durations_s') or
            not all(math.isfinite(v) and v>0 for k,v in asdict(p).items()
                if k not in ('comparator_noise_rms_v','reference_idle_a','bit_durations_s')) or
            min(p.comparator_noise_rms_v,p.reference_idle_a)<0):
        raise ValueError('Positive physical hypotheses and a comparator interval inside each bit required')
    durations=np.asarray(p.bit_durations_s,float)
    if durations.shape!=(10,) or not np.all(np.isfinite(durations)) or np.any(durations<=p.comparator_s):
        raise ValueError('Ten bit intervals longer than comparator allocation required')
    conversion_s=float(sum(durations));offsets=np.r_[0.,np.cumsum(durations[:-1])]
    required=p.acquisition_s+conversion_s+p.reset_control_s
    period=float(np.min(np.diff(t))) if len(t)>1 else required
    if period<required:
        raise ValueError('Conversion/acquisition/reset schedule does not fit the sampling period')
    # Reference forcing is midpoint-held over the DAC-settle and comparator
    # intervals, plus the inter-conversion interval; no truth reference samples.
    bit_start=t[:,None]+offsets
    settle=durations-p.comparator_s
    mid=np.stack((bit_start+settle/2,bit_start+settle+p.comparator_s/2),axis=-1)
    targets=np.asarray(reference_at(mid.ravel())).reshape(mid.shape)
    rails=np.asarray(rail_at(mid.ravel())).reshape(mid.shape)
    sample_ref=np.asarray(reference_at(t));sample_rails=np.asarray(rail_at(t))
    previous_ends=np.r_[t[0]-p.acquisition_s,t[:-1]+conversion_s]
    idle_mid=(previous_ends+t)/2
    idle_ref=np.asarray(reference_at(idle_mid));idle_rail=np.asarray(rail_at(idle_mid))
    if min(targets.min(),sample_ref.min(),idle_ref.min(),rails.min(),sample_rails.min(),idle_rail.min())<=0:
        raise ValueError('Positive reference and loaded rail required')
    rng=np.random.default_rng(seed)
    thermal=math.sqrt(2*1.380649e-23*p.temperature_k/p.sample_cap_per_leg_f)
    # Draw per-conversion rows so extending the capture preserves the entire
    # earlier physical noise realization, including both I/Q components.
    draws=rng.normal(size=(len(z),22)) if noise else np.zeros((len(z),22))
    held_noise=thermal*(draws[:,0]+1j*draws[:,1])
    comparator_noise=p.comparator_noise_rms_v*(draws[:,2:12]+1j*draws[:,12:22])
    held=0j;reference=float(sample_ref[0]);initial_reference=reference
    last_code=-1-1j;dac=last_code*reference;last_time=float(previous_ends[0])
    words=np.empty((len(z),2),np.int64)
    applied=np.empty_like(z)
    # Each segment describes the exact reference recovery before the next load
    # event. It supports charge-preserving supply-current resampling downstream.
    segments=[];charge_drawn=0.;signed_recharge=0.;positive_recharge=0.
    ref_min=reference;ref_max=reference;dac_error=0.;acq_error=[];peak_source=0.;limited_segments=0

    def advance(time,duration,target,rail,code):
        nonlocal reference,dac,signed_recharge,positive_recharge,peak_source,limited_segments,ref_min,ref_max
        r=p.reference_r_ohm*3.3/rail;tau=p.dac_tau_s*3.3/rail
        initial=reference
        peak_source=max(peak_source,min(p.reference_limit_a,max(0.,(target-reference)/r)))
        limited_segments+=int(abs(target-reference)/r>p.reference_limit_a)
        reference,dac,charge=recover(reference,dac,target,code,duration,
            r=r,c=p.reference_cap_f,limit=p.reference_limit_a,tau=tau)
        segments.append((time,duration,initial,target,r,charge))
        signed_recharge+=charge;positive_recharge+=max(0.,charge)
        ref_min=min(ref_min,initial,reference);ref_max=max(ref_max,initial,reference)

    for i in range(len(z)):
        advance(last_time,float(t[i]-last_time),float(idle_ref[i]),float(idle_rail[i]),last_code)
        first,last=(start[i],z[i]) if input_control is None else input_control.acquire(i,start[i],z[i],float(t[i]))
        applied[i]=last
        acquisition_tau=p.sample_resistance_ohm*p.sample_cap_per_leg_f*3.3/sample_rails[i]
        decay=math.exp(-p.acquisition_s/acquisition_tau)
        slope=(last-first)/p.acquisition_s
        held=last-slope*acquisition_tau+(held-first+slope*acquisition_tau)*decay
        acq_error.append(abs(held-last))
        observed=held+held_noise[i]+sample_ref[i]/1024*(1+1j)
        accepted_i=accepted_q=0
        for bit,mask in enumerate((512,256,128,64,32,16,8,4,2,1)):
            trial_i=accepted_i+mask;trial_q=accepted_q+mask
            code=complex((trial_i-512)/512,(trial_q-512)/512)
            charge=p.dac_effective_cap_f*(abs(code.real-last_code.real)+abs(code.imag-last_code.imag))*reference
            charge_drawn+=charge;reference-=charge/p.reference_cap_f
            if reference<=0:raise ValueError('Reference reservoir collapsed under trial charge')
            ref_min=min(ref_min,reference)
            advance(float(bit_start[i,bit]),float(settle[bit]),float(targets[i,bit,0]),float(rails[i,bit,0]),code)
            dac_error=max(dac_error,abs(dac-code*reference))
            margin=observed-dac+comparator_noise[i,bit]
            if margin.real>0 or (margin.real==0 and trial_i%2==0):accepted_i=trial_i
            if margin.imag>0 or (margin.imag==0 and trial_q%2==0):accepted_q=trial_q
            advance(float(bit_start[i,bit]+settle[bit]),p.comparator_s,
                float(targets[i,bit,1]),float(rails[i,bit,1]),code)
            last_code=code
        words[i]=((accepted_i-512)*4,(accepted_q-512)*4)
        last_time=float(t[i]+conversion_s)
        if input_control is not None:
            input_control.observe(i,complex(words[i,0],words[i,1])/2048,last_time)
    duration=last_time-previous_ends[0]
    source_mean=positive_recharge/duration
    ideal=np.clip(np.rint(np.column_stack((applied.real,applied.imag))/sample_ref[:,None]*512),-512,511)
    error=words/4-ideal
    report=dict(parameters=asdict(p),native_bits=10,transport_bits=12,
        maximum_rate_hz=1/required,schedule_margin_s=period-required,
        conversion_latency_s=conversion_s,
        sampling_thermal_rms_per_component_v=thermal,noise_enabled=noise,
        code_error_rms_lsb=float(np.sqrt(np.mean(error**2))),maximum_code_error_lsb=float(max(abs(error).ravel())),
        acquisition_error_rms_v=float(np.sqrt(np.mean(np.array(acq_error)**2))),
        reference_interval_v=[ref_min,ref_max],maximum_dac_following_error_at_decision_v=dac_error,
        reference_charge_drawn_c=charge_drawn,signed_reference_recharge_c=signed_recharge,
        reference_charge_balance_residual_c=signed_recharge-charge_drawn-p.reference_cap_f*(reference-initial_reference),
        reference_source_average_a=source_mean,reference_source_peak_a=peak_source,
        reference_with_bias_average_a=source_mean+p.reference_idle_a,
        reference_with_bias_peak_a=peak_source+p.reference_idle_a,
        fits_6ma_reference_owner_peak=peak_source+p.reference_idle_a<=.006,
        current_limited_segments=limited_segments,
        scope='Predictive conditional charge/settling/decision recurrence, not fitted silicon. Effective CDAC charge uses absolute code steps and dissipative switching; return-charge reuse, capacitor mismatch and comparator regeneration time are unmodeled. Input acquisition uses linear endpoints; half-LSB midpoint convention is assigned. The fixed comparator interval is an allocation, not demonstrated metastability performance.')
    trace=dict(segments=np.asarray(segments),reference_cap_f=p.reference_cap_f,
        reference_limit_a=p.reference_limit_a,mean_source_a=source_mean)
    return words,report,trace


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


def load_response(trace,candidate,*,grid_s=.25e-9,supply_current_tau_s=.2e-9,reference_input=None,supply_sign=1.,sensitivity_ps_per_mv=.1):
    """Reference source current -> same PDN -> rail, clock-delay, reference.

    AC overlay retains the conservative full planning DC load. Its extra DC
    stress relative to the predicted reference draw is explicitly reported;
    no additional mean reference current is charged on top of the 40 mA owner.
    """
    delay_gain=supply_delay_gain(sensitivity_ps_per_mv,supply_sign)
    segments=trace['segments'];starts=segments[:,0];ends=starts+segments[:,1]
    c=trace['reference_cap_f'];limit=trace['reference_limit_a']
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
    # Two-microsecond guards suppress periodic wrap; report guard comparison in
    # tests rather than treating a periodic FFT as an unqualified transient.
    guard=math.ceil(2e-6/grid_s);size=2**math.ceil(math.log2(len(current)+2*guard))
    stimulus=np.zeros(size);stimulus[guard:guard+len(current)]=current-mean
    frequency=np.fft.rfftfreq(size,grid_s);spectrum=np.fft.rfft(stimulus)
    drive=spectrum/(1+2j*np.pi*frequency*supply_current_tau_s)
    coupled=None if reference_input is None else coupled_reference_load_transfer(frequency,candidate,**reference_input)
    response=drive*(local_impedance(frequency,candidate) if coupled is None else coupled['rail_v_per_a'])
    # Retain the physical relaxation tail rather than hard-resetting the rail
    # and clock perturbation at the final ADC code. A later TX queries this same
    # absolute-time trajectory, including the quiet interval before launch.
    end=guard+len(current)+guard
    rail=np.fft.irfft(response,n=size)[guard:end]
    delay=np.fft.irfft(response*delay_gain/(1+1j*frequency/1e9),n=size)[guard:end]
    reference=np.fft.irfft(response*.1/(1+1j*frequency/10e6),n=size)[guard:end]
    times=beginning+(np.arange(len(rail))+.5)*grid_s
    result=dict(times_s=times,rail_v=rail,delay_s=delay,reference_fraction=reference,
        resolved_offset_hz=.5/grid_s)
    if coupled is not None:
        result['input_v']=np.fft.irfft(drive*coupled['input_v_per_a'],n=size)[guard:end]
        result['return_v']=np.fft.irfft(drive*coupled['return_v_per_a'],n=size)[guard:end]
        if 'input_leg_v_per_a' in coupled:
            result['input_leg_v']=np.fft.irfft(drive[:,None]*coupled['input_leg_v_per_a'],n=size,axis=0)[guard:end]
    report=dict(grid_s=grid_s,supply_current_tau_s=supply_current_tau_s,
        coupled_reference_input=reference_input,supply_sensitivity_sign=supply_sign,supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        direct_input_voltage_in_timing=False,
        sampled_source_average_a=mean,integrated_source_charge_c=float(sum(current)*grid_s),
        charge_resampling_residual_c=float(sum(current)*grid_s-cumulative[-1]),
        rail_interval_v=[float(min(rail)),float(max(rail))],rail_rms_v=float(np.sqrt(np.mean(rail**2))),
        clock_delay_rms_s=float(np.sqrt(np.mean(delay**2))),
        reference_fraction_rms=float(np.sqrt(np.mean(reference**2))),
        scope='Local reference recharge port only, superposed with host ripple at full planning DC. Positive source charge is conserved; sink current receives no supply-energy credit. Assigned 200 ps supply-current pole requires an internal charge path; not a validated buffer. FFT guards, finite grid and linear fixed PDN do not qualify physical peak current or broadband transistor noise.')
    if coupled is not None:
        report.update(input_voltage_abs_peak_v=float(max(abs(result['input_v']))),
            input_voltage_rms_v=float(np.sqrt(np.mean(result['input_v']**2))),
            return_voltage_abs_peak_v=float(max(abs(result['return_v']))),
            scope=report['scope']+' Coupled tied-return REF_IN voltage is exposed; the delivered-clock consumer must separately solve perturbed threshold events.')
    if 'input_leg_v' in result:
        report['input_leg_voltage_abs_peak_v']=np.max(abs(result['input_leg_v']),axis=0).tolist()
    return result,report


def response_change(updated,previous):
    if previous is None:return None,None,False
    # Compare the common physical capture, without extrapolating a terminal
    # value across an infinitesimal change of the capture endpoint.
    common=(updated['times_s']>=previous['times_s'][0]) & (updated['times_s']<=previous['times_s'][-1])
    prior=np.interp(updated['times_s'][common],previous['times_s'],previous['rail_v'])
    difference=updated['rail_v'][common]-prior
    rms=float(np.sqrt(np.mean(difference**2)));peak=float(max(abs(difference)))
    return rms,peak,rms<=1e-6 and peak<=20e-6


def tone_precision(environment,parameters,*,bin_number=499,count=2048,amplitude=.65):
    """Converter precision at substantial swing, with its own PDN feedback.

    A fitted sine/cosine/DC removes gain, phase and offset only. Residual includes
    nonlinear distortion, noise and jitter. This is not a waveform equalizer.
    """
    from selected_rf import DeliveredClock,reference_at,rail_at
    fs=environment['carrier_hz']/64;frequency=fs*bin_number/count
    ideal=(np.arange(count)+1)/fs
    aperture=np.random.default_rng(411).normal(0,10e-12,count)
    response=None;history=[];converged=False
    for iteration in range(4):
        e=environment if response is None else dict(environment,local_load_response=response)
        actual=ideal+DeliveredClock(e).crossing_error(ideal,e['carrier_hz'])+aperture
        values=amplitude*np.exp(2j*np.pi*frequency*actual)
        starts=amplitude*np.exp(2j*np.pi*frequency*(actual-parameters.acquisition_s))
        words,converter,trace=paired_sar(values,starts,actual,
            lambda t:reference_at(e,t),lambda t:rail_at(e,t),parameters=parameters)
        updated,load=load_response(trace,e['network'])
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
    return dict(frequency_hz=frequency,sample_hz=fs,input_peak_per_component_v=amplitude,
        measured_samples_per_component=len(observed),residual_rms_v=residual.tolist(),
        sinad_db=sinad.tolist(),fullscale_normalized_enob=enob.tolist(),
        fitted_peak_v=fitted_peak.tolist(),fitted_offset_v=coefficients[2].tolist(),
        meets_assigned_8enob=bool(min(enob)>=8),numerical_feedback_converged=converged,
        iterations=history,converter=converter,load_response=load,
        minimum_sampled_rail_v=float(min(rail_at(e,actual))),
        scope='Known sine characterization, not protocol training. I and Q are tested together against their shared reference. Full-scale-normalized ENOB includes residual harmonic distortion and noise after fitting only a fundamental and DC. This stimulus has its own reference-current/PDN feedback; it does not borrow an OFDM load trajectory. Assigned noise, poles, midpoint-held supply sensitivity and comparator interval still need physical evidence.')
