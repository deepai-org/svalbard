"""Selected RF transfer boundaries under the shared baseline environment.

This is a circuit-requirement model, not a transistor or protocol qualification.
No receiver gets the phase realization, converter timestamps or payload truth.
Known DATA training and ideal frame boundaries remain explicit fixture aids.
"""
import math
from copy import deepcopy
import numpy as np
from scipy import signal

from behavioral import bandlimited_samples, rf_tx_resistive_port, rf_tx_compliance_budget
from oscillator_noise import PhaseNoise
from protocol_signals import he20
from ble_packet import third_order_frontend,receiver_pga_peak,receiver_lna_gain,receiver_pga_response
from tx_output_stage import output_envelope
from tx_output_candidate import PARAMETERS as TX_PARAMETERS


def _analog_prototype(family):
    if family == 'rx_finite_zero':
        b, a = signal.ellip(5, 1, 36.40776933523119, 1, analog=True)
    elif family == 'rx_all_pole_control':
        b, a = signal.butter(5, 1, analog=True)
    elif family == 'tx_third_order':
        b, a = signal.butter(3, 1, analog=True)
    else:
        raise ValueError('Unknown analog transfer family')
    return b,a


def analog_modes(family,*,integrator_ratio=None,retune_ratio=None):
    b,a=_analog_prototype(family)
    if integrator_ratio is not None:
        if not math.isfinite(integrator_ratio) or integrator_ratio<=0:
            raise ValueError('Positive finite integrator pole/cutoff ratio required')
        if retune_ratio is not None:
            if not math.isfinite(retune_ratio) or retune_ratio<=0:
                raise ValueError('Positive finite characterized ratio required')
            # Inverse-map desired zeros/poles through q=z+z*z/rho.
            # Coefficients remain real; this is an unconstrained tuning candidate,
            # not proof the physical biquad weights can realize these values.
            zeros,poles,_=signal.tf2zpk(b,a)
            zeros=zeros+zeros**2/retune_ratio;poles=poles+poles**2/retune_ratio
            gain=(b[-1]/a[-1])*np.prod(-poles)/np.prod(-zeros)
            b,a=signal.zpk2tf(zeros,poles,float(np.real(gain)))
    elif retune_ratio is not None:
        raise ValueError('Retuning requires a finite integrator model')
    residues, poles, direct = signal.residue(b, a)
    if len(direct):
        raise ValueError('Strictly proper analog response required')
    if integrator_ratio is not None:
        # Replace ideal 1/z integrators by 1/[z*(1+z/rho)]. Each prototype
        # mode r/(q-p) becomes two modes at the quadratic roots. This explicit
        # surrogate is not a measured op-amp GBW or a universal active-RC law.
        slow=2*poles/(1+np.sqrt(1+4*poles/integrator_ratio))
        fast=-integrator_ratio-slow
        residues=np.r_[residues/(1+2*slow/integrator_ratio),residues/(1+2*fast/integrator_ratio)]
        poles=np.r_[slow,fast]
    return residues, poles


def rx_filter_state_space(*,order=(0,1,2),zero_pairing=(0,1),integrator_ratio=None,retune_ratio=None,
                          family='rx_finite_zero'):
    """Explicit unity-DC sections with voltage-like LP/BP integrator states.

    Section 0 is the real pole; 1/2 are the low/high-frequency biquads.
    LP'=w*BP, BP'=w*(u-LP-BP/Q); feedforward forms the notch numerator.
    Independent input-voltage noise excites each integrator through w. Summers
    and the extra finite-bandwidth states are noiseless hypotheses here.
    This pins state scaling; arbitrary modal amplitudes are not called voltages.
    """
    if sorted(order)!=[0,1,2] or sorted(zero_pairing)!=[0,1]:
        raise ValueError('A permutation of three sections and two zero pairs is required')
    if retune_ratio is not None and integrator_ratio is None:
        raise ValueError('Retuning requires a finite integrator model')
    for value in (integrator_ratio,retune_ratio):
        if value is not None and (not math.isfinite(value) or value<=0):
            raise ValueError('Positive finite integrator ratios required')
    if family not in ('rx_finite_zero','rx_all_pole_control'):raise ValueError('Five-pole state-space family')
    zeros,poles,_=signal.tf2zpk(*_analog_prototype(family))
    real=float(poles[np.argmin(abs(poles.imag))].real)
    pairs=sorted(poles[poles.imag>0],key=abs);zero_pairs=sorted(zeros[zeros.imag>0],key=abs)
    if retune_ratio is not None:
        real+=real**2/retune_ratio
        pairs=[v+v*v/retune_ratio for v in pairs]
        zero_pairs=[v+v*v/retune_ratio for v in zero_pairs]
    sections=[(np.array([[real]]),np.array([-real]),np.array([1.]),0.,np.array([-real]),['pole'])]
    for index,pole in enumerate(pairs):
        w=abs(pole);a1=-2*pole.real
        if family=='rx_finite_zero':
            zero=zero_pairs[zero_pairing[index]]
            b0=abs(zero)**2;b1=-2*zero.real;k=w*w/b0
            c=np.array([k*(b0/(w*w)-1),k*(b1-a1)/w]);d=k
        else:
            c=np.array([1.,0.]);d=0.
        sections.append((np.array([[0.,w],[-w,-a1]]),np.array([0.,w]),
            c,d,np.array([w,w]),
            [f'biquad{index+1}_lp',f'biquad{index+1}_bp']))
    A=np.zeros((0,0));B=np.zeros(0);C=np.zeros(0);D=1.;noise=[];labels=[];observers=[];resistor_weights=[];resistor_loads=[]
    for index in order:
        a,bi,c,d,namescale,names=sections[index];old=len(B);new=len(bi)
        # Absolute local resistor currents into ideal virtual-ground summers.
        # Columns are five integration voltages, three section outputs, input.
        loads=np.zeros((new,9));loads[:,old:old+new]=abs(a)
        loads[:,8 if old==0 else 5+len(observers)-1]=abs(bi)
        resistor_loads.extend(loads)
        A=np.block([[A,np.zeros((old,new))],[np.outer(bi,C),a]])
        B=np.r_[B,bi*D];C=np.r_[d*C,c];D*=d
        noise.extend(namescale);labels.extend(names)
        # One resistor per nonzero signed local summing coefficient; ideal
        # polarity conversion/summers are separate unpriced assumptions.
        resistor_weights.extend((np.sum(abs(a),axis=1)+abs(bi))/namescale)
        observers.append((f'section{index}_output',C.copy(),float(D)))
    N=np.diag(noise);count=len(B)
    O=np.vstack([np.eye(count)]+[np.pad(c,(0,count-len(c)))[None,:] for _,c,_ in observers])
    direct=np.r_[np.zeros(count),[d for _,_,d in observers]]
    labels += [name for name,_,_ in observers]
    if integrator_ratio is not None:
        rho=integrator_ratio
        A=np.block([[np.zeros_like(A),np.eye(count)],[rho*A,-rho*np.eye(count)]])
        B=np.r_[np.zeros(count),rho*B];N=np.vstack([np.zeros_like(N),rho*N])
        C=np.r_[C,np.zeros(count)];O=np.c_[O,np.zeros_like(O)]
        # x'=w*z: z is the bandwidth-limited integrator drive voltage in
        # this chosen cascade realization, rather than an unscaled derivative.
        O=np.vstack([O,np.c_[np.zeros((count,count)),np.diag(1/np.asarray(noise))]])
        direct=np.r_[direct,np.zeros(count)]
        labels += [name+'_drive' for name in labels[:count]]
    return dict(family=family,A=A,B=B,C=C,D=D,noise_inputs=N,observers=O,observer_direct=direct,
        observer_names=labels,noise_names=labels[:count],order=list(order),zero_pairing=list(zero_pairing),
        normalized_integrator_rates=np.asarray(noise),resistor_conductance_weights=np.asarray(resistor_weights),
        normalized_resistor_load_matrix=np.asarray(resistor_loads))


def filter_settling_requirement(*, family, cutoff_hz, past_input_bound=1., error_budget=1/1024,
                                integrator_ratio=None,retune_ratio=None):
    """Sufficient decay time for bounded *linear* filter history, not bias wake.

    For H(s)=sum(r/(s-p)), |u(t<0)|<=U gives each normalized modal
    state magnitude <=U/(-Re(p)). After histories receive identical forcing,
    their output difference from a zero-history reference is bounded by
    U*sum(|r|/(-Re(p))*exp(Re(p)*2*pi*fc*t)). New input is unrestricted
    within the linear model; this bound applies only to the old-history error.
    Units must already refer to the same gain/observation point. Arbitrary
    charged capacitors, saturation and coefficient-change state mapping are
    outside this bounded-input-history contract.
    """
    if not all(math.isfinite(v) and v > 0 for v in (cutoff_hz,past_input_bound,error_budget)):
        raise ValueError('Positive finite cutoff, history bound and error budget required')
    residues,poles=analog_modes(family,integrator_ratio=integrator_ratio,retune_ratio=retune_ratio)
    decay=-poles.real*2*math.pi*cutoff_hz
    if np.any(decay<=0):raise ValueError('Stable filter modes required')
    weights=past_input_bound*abs(residues)/(-poles.real)
    def bound(t):return float(np.sum(weights*np.exp(-decay*t)))
    lo=0.;hi=max(0.,math.log(max(sum(weights)/error_budget,1.))/min(decay))
    for _ in range(64):
        mid=(lo+hi)/2
        if bound(mid)>error_budget:lo=mid
        else:hi=mid
    # Ensure the rounded returned deadline remains on the conservative side.
    while bound(hi)>error_budget:hi=float(np.nextafter(hi,np.inf))
    return dict(family=family,cutoff_hz=cutoff_hz,integrator_ratio=integrator_ratio,
        retune_ratio=retune_ratio,past_input_bound=past_input_bound,
        error_budget=error_budget,settling_s=float(hi),modal_weights=weights.tolist(),
        decay_per_s=decay.tolist(),bound_at_deadline=bound(hi))


def analog_filter(values, sample_hz, *, family, cutoff_hz, interpolation='zoh',
                  initial_state=None,state_capture=None,integrator_ratio=None,retune_ratio=None):
    """Continuous analog modes with exact constant or linear forcing per step.

    ZOH returns the state at the end of each held interval (legacy convention).
    Linear forcing returns states at the input timestamps, starting from zero.
    Neither method resets at symbol boundaries or uses a fitted filter response.
    Saved normalized modal states preserve history across records with identical
    coefficients. ZOH commits the end of the last held interval; linear forcing
    commits the last input timestamp (repeat that endpoint when continuing).
    """
    if not all(math.isfinite(v) and v > 0 for v in (sample_hz, cutoff_hz)) or interpolation not in ('zoh','linear'):
        raise ValueError('Positive rates and a supported forcing interpolation required')
    values=np.asarray(values)
    if values.ndim!=1 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError('Finite nonempty forcing vector required')
    residues, poles = analog_modes(family,integrator_ratio=integrator_ratio,retune_ratio=retune_ratio)
    if np.any(poles.real>=0):raise ValueError('Unstable filter realization cannot qualify a waveform')
    modes=np.zeros(len(poles),complex)
    if initial_state is not None:
        if (initial_state.get('family')!=family or initial_state.get('cutoff_hz')!=cutoff_hz or
                initial_state.get('integrator_ratio')!=integrator_ratio or initial_state.get('retune_ratio')!=retune_ratio):
            raise ValueError('Filter coefficient change requires explicit state mapping')
        encoded=np.asarray(initial_state.get('modes'),float)
        if encoded.shape!=(len(poles),2) or not np.all(np.isfinite(encoded)):
            raise ValueError('Finite compatible filter modal state required')
        modes=encoded[:,0]+1j*encoded[:,1]
    exponent = poles * 2 * math.pi * cutoff_hz / sample_hz
    result=np.zeros(len(values),complex);final=[]
    for residue,pole,e,initial in zip(residues,poles,exponent,modes):
        if interpolation=='zoh':
            out,_=signal.lfilter([np.expm1(e)/pole],[1,-np.exp(e)],values,zi=[np.exp(e)*initial])
        else:
            # expm1(e)-e loses precision for small steps; use its series.
            b=(e/2+e*e/6+e**3/24+e**4/120+e**5/720)/pole if abs(e)<1e-3 else (np.expm1(e)-e)/(pole*e)
            a=np.expm1(e)/pole-b
            out,_=signal.lfilter([b,a],[1,-np.exp(e)],values,zi=[initial-b*values[0]])
        result+=residue*out
        final.append([float(out[-1].real),float(out[-1].imag)])
    if state_capture is not None:
        state_capture.update(family=family,cutoff_hz=cutoff_hz,modes=final,
            integrator_ratio=integrator_ratio,retune_ratio=retune_ratio)
    return result


def analog_hold_at(values, edges, times, *, family, cutoff_hz,integrator_ratio=None):
    """Exact analog reconstruction at queries after nonuniform DAC transitions.

    No rounding DAC edges onto the analysis grid: such rounding would inject
    artificial timing error larger than the aperture budget being investigated.
    Initial state is zero before the first edge; final code holds indefinitely.
    """
    values=np.asarray(values,complex);edges=np.asarray(edges,float);times=np.asarray(times,float)
    if (values.ndim!=1 or edges.shape!=values.shape or len(values)<1 or times.ndim!=1 or
            np.any(np.diff(edges)<=0) or not np.all(np.isfinite(values)) or
            not np.all(np.isfinite(edges)) or not np.all(np.isfinite(times)) or
            not math.isfinite(cutoff_hz) or cutoff_hz<=0):
        raise ValueError('Finite held values, strictly increasing edges and positive cutoff required')
    residues,poles=analog_modes(family,integrator_ratio=integrator_ratio);rate=2*math.pi*cutoff_hz
    if np.any(poles.real>=0):raise ValueError('Stable reconstruction filter required')
    states=np.zeros((len(edges),len(poles)),complex)
    for i in range(1,len(edges)):
        exponent=poles*rate*(edges[i]-edges[i-1])
        states[i]=states[i-1]*np.exp(exponent)+values[i-1]*np.expm1(exponent)/poles
    index=np.searchsorted(edges,times,side='right')-1
    valid=index>=0;index=np.maximum(index,0)
    elapsed=np.maximum(0,times-edges[index]);result=np.zeros(len(times),complex)
    for j,(residue,pole) in enumerate(zip(residues,poles)):
        exponent=pole*rate*elapsed
        result+=residue*(states[index,j]*np.exp(exponent)+values[index]*np.expm1(exponent)/pole)
    return np.where(valid,result,0j)


def native_adc(values, reference, *, enob=8., seed=1900, noise=True):
    """Signed native 10-bit transfer, left-justified in signed 12-bit words.

    Reference is differential half-range in volts. Excess ENOB noise is an
    assigned input-referred noise expressed as a fraction of this reference;
    it does not demonstrate SAR settling, DNL/INL or comparator performance.
    """
    z = np.asarray(values, complex); reference = np.asarray(reference, float)
    if (not 1 <= enob <= 10 or not np.all(np.isfinite(z)) or
            not np.all(np.isfinite(reference)) or np.any(reference <= 0)):
        raise ValueError('Finite input, positive reference and 1..10 ENOB required')
    normalized = z/reference
    if noise:
        sigma = math.sqrt(max(0., 2**(2-2*enob)-(1/512)**2)/12)
        rng = np.random.default_rng(seed)
        normalized = normalized + sigma*(rng.normal(size=z.shape)+1j*rng.normal(size=z.shape))
    raw = np.stack((np.rint(normalized.real*512), np.rint(normalized.imag*512)), axis=-1)
    clipped = (raw < -512) | (raw > 511)
    words = np.clip(raw, -512, 511).astype(np.int64)*4
    return words, dict(clipped_components=int(clipped.sum()),
        component_count=int(raw.size),native_bits=10,transport_bits=12,
        enob_hypothesis=enob,rounding='nearest, ties to even',
        low_two_transport_bits_zero=bool(np.all(words % 4 == 0)))


def output_enable_envelope(times,launch_s,stop_s,*,fault=False,rise_tau_s=50e-9,normal_fall_s=20e-9):
    """Assigned generic unmute/normal-mute slew; abrupt fault control retained."""
    if (not all(math.isfinite(x) for x in (launch_s,stop_s,rise_tau_s,normal_fall_s)) or
            stop_s<launch_s or rise_tau_s<=0 or normal_fall_s<=0 or type(fault) is not bool):
        raise ValueError('Ordered finite launch/stop and positive slew intervals required')
    t=np.asarray(times,float)
    if not np.all(np.isfinite(t)):raise ValueError('Finite envelope query times required')
    rise=-np.expm1(-np.maximum(0.,t-launch_s)/rise_tau_s)
    # Mute begins at the observed stop event, never before it. Normal closure
    # may extend RF energy by normal_fall_s; a fault uses an ideal hard cut.
    fall=(t<stop_s).astype(float) if fault else np.clip(1-(t-stop_s)/normal_fall_s,0.,1.)
    return rise*fall


def native_dac(words, reference):
    """12-bit transport to saturated 10-bit code; no modulo wrapping."""
    words = np.asarray(words); reference = np.asarray(reference, float)
    if (words.ndim != 2 or words.shape[1] != 2 or
            not np.issubdtype(words.dtype, np.integer) or
            np.any(words < -2048) or np.any(words > 2047) or
            not np.all(np.isfinite(reference)) or np.any(reference <= 0)):
        raise ValueError('Signed 12-bit I/Q words and positive reference required')
    rounded = np.rint(words/4)
    native = np.clip(rounded, -512, 511)
    result = (native[:, 0]+1j*native[:, 1])/512*reference
    return result, dict(saturated_components=int(np.sum(rounded != native)),
        rounding='nearest, ties to even',native_bits=10,transport_bits=12)


def rail_on_uniform_grid(environment,count,sample_hz,*,start_s=0.):
    """Exact finite-tone grid via one coherent FFT; no waveform interpolation."""
    from fractions import Fraction
    tones=environment['host_spectrum']['tones']
    if type(count) is not int or count<1 or not math.isfinite(sample_hz) or sample_hz<=0:
        raise ValueError('Positive sample count and sample rate required')
    if not math.isfinite(start_s):raise ValueError('Finite absolute grid start required')
    ratios=[Fraction(str(t['frequency_hz']))/Fraction(str(sample_hz)) for t in tones]
    length=math.lcm(*(r.denominator for r in ratios))
    times=start_s+np.arange(count)/sample_hz
    if length>2**22:return rail_at(environment,times)
    spectrum=np.zeros(length//2+1,complex)
    for tone,ratio in zip(tones,ratios):
        k=(ratio.numerator*(length//ratio.denominator))%length
        value=tone['clock_rail_voltage_peak_v']*np.exp(1j*(tone['voltage_phase_rad']+2*np.pi*tone['frequency_hz']*start_s))
        if k>length//2:k=length-k;value=value.conjugate()
        spectrum[k]+=value.real if k==0 or (length%2==0 and k==length//2) else value/2
    wave=np.fft.irfft(spectrum,n=length)*length
    return environment['ledger']['local_payload_clock_core_rail_v']+np.resize(wave,count)+load_value(environment,times,'rail_v')


def rail_at(environment, times):
    return load_value(environment,times,'rail_v') + np.full_like(times, environment['ledger']['local_payload_clock_core_rail_v'], dtype=float) + sum(
        t['clock_rail_voltage_peak_v']*np.cos(2*math.pi*t['frequency_hz']*times+t['voltage_phase_rad'])
        for t in environment['host_spectrum']['tones'])


def reference_target_v(environment):
    """Absolute reference owner; independent normalized fixtures default to 1 V."""
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    parameters=environment.get('reference_supply_parameters',{})
    if bound and 'target_v' not in parameters:
        raise ValueError('Design-bound reference requires target_v')
    target=parameters.get('target_v',1.)
    if isinstance(target,bool) or not isinstance(target,(int,float)) or not math.isfinite(target) or target<=0:
        raise ValueError('Positive finite reference target required')
    return target


def reference_scale_at(environment, times):
    """Dimensionless reference motion for transfers allocated at the target."""
    reference_target_v(environment)
    return load_value(environment,times,'reference_fraction') + np.ones_like(times, dtype=float) + sum(a*np.cos(2*math.pi*f*times+p)
                   for f, a, p in environment['reference_fraction_tones'])


def reference_at(environment, times):
    """Absolute converter-reference voltage, including fractional forcing."""
    return reference_target_v(environment)*reference_scale_at(environment,times)


def prepared_supply_functions(environment):
    """Snapshot equivalent rail/reference samplers for a fixed solve iteration.

    Cache coefficients and contiguous response vectors once. Small asynchronous
    event queries otherwise repeat Python tone loops and may copy strided FFT
    columns on every interpolation. No time-grid or spectral truncation changes.
    Rebuild after changing the environment or its feedback response.
    """
    response=environment.get('local_load_response')
    def prepare(dc,tones,field):
        coeff=np.array(tones,dtype=float,copy=True).reshape(-1,3)
        omega=2*np.pi*coeff[:,0];amp=coeff[:,1];phase=coeff[:,2]
        if response is not None:
            grid=np.array(response['times_s'],dtype=float,copy=True,order='C')
            values=np.array(response[field],dtype=float,copy=True,order='C')
            background=response.get('background',{}).get(field,0.)
        def sample(times):
            t=np.asarray(times,float)
            if t.size<=256:
                value=dc+np.sum(amp*np.cos(t[...,None]*omega+phase),axis=-1)
            else:
                value=np.full_like(t,dc)
                for w,a,p in zip(omega,amp,phase):value+=a*np.cos(w*t+p)
            if response is not None:
                value=value+np.interp(t,grid,values,left=background,right=background)
            return value
        return sample
    rail=prepare(environment['ledger']['local_payload_clock_core_rail_v'],
        [(t['frequency_hz'],t['clock_rail_voltage_peak_v'],t['voltage_phase_rad'])
         for t in environment['host_spectrum']['tones']],'rail_v')
    target=reference_target_v(environment)
    reference_fraction=prepare(1.,environment['reference_fraction_tones'],'reference_fraction')
    def reference(times):return target*reference_fraction(times)
    return rail,reference


def load_value(environment,times,field):
    response=environment.get('local_load_response')
    if response is None:return np.zeros_like(times,dtype=float)
    background=response.get('background',{}).get(field,0.)
    return np.interp(times,response['times_s'],response[field],left=background,right=background)


class PeriodicEdgePhase:
    """Continuous phase from ordered periodic rising edges; no missing-edge repair.

    Phase advances linearly between measured mathematical events. This is a
    timing abstraction, not a reconstructed buffer waveform or duty cycle.
    """
    def __init__(self,record):
        self.carrier=float(record['carrier_hz']);self.period=float(record['period_s'])
        self.edges=np.asarray(record['edges_s'],float)
        if (not math.isfinite(self.carrier) or self.carrier<=0 or
                not math.isfinite(self.period) or self.period<=0 or self.edges.ndim!=1 or
                not len(self.edges) or not np.all(np.isfinite(self.edges)) or
                abs(len(self.edges)-self.carrier*self.period)>1e-6):
            raise ValueError('Complete finite periodic clock edge record required')
        self.grid=np.r_[self.edges,self.edges[0]+self.period]
        spacing=np.diff(self.grid)
        if np.any(spacing<=0):raise ValueError('Clock edges must remain ordered across the period boundary')
        self.index=np.arange(len(self.grid))
        self.minimum_rate_ratio=1/(self.carrier*max(spacing))
        self.phase_bound=float(max(abs(2*np.pi*(self.index-self.carrier*self.grid))))
        self.maximum_offset_hz=self.carrier/2  # Edge-information Nyquist, not a bandlimit.

    def phase(self,times):
        t=np.asarray(times,float)
        if not np.all(np.isfinite(t)):raise ValueError('Finite clock query times required')
        within=self.edges[0]+np.remainder(t-self.edges[0],self.period)
        cycles=np.interp(within,self.grid,self.index)
        return 2*np.pi*(cycles-self.carrier*within)


def coupled_load_clock_edges(environment,response):
    """Resolve finite load-voltage perturbations around accepted input events.

    A derivative bound guarantees one root in each local bracket. This does
    not independently exclude additional crossings elsewhere in each UI.
    Assigned source/input phase noise remains a later small perturbation.
    """
    record=environment['reference_threshold'];carrier=environment['carrier_hz']
    period=record['period_s'];base=np.asarray(record['input_edges_s'])
    times=np.asarray(response['times_s']);voltage=np.asarray(response['input_v'])
    delay=np.asarray(response['delay_s'])
    background=response.get('background',{})
    quiet_voltage=background.get('input_v',0.);quiet_delay=background.get('delay_s',0.)
    if (times.ndim!=1 or len(times)<2 or voltage.shape!=times.shape or delay.shape!=times.shape or
            np.any(np.diff(times)<=0) or not all(np.all(np.isfinite(x)) for x in (times,voltage,delay))):
        raise ValueError('Finite ordered load voltage/delay trajectory required')
    cycles=np.arange(math.floor(times[0]/period)-2,math.ceil(times[-1]/period)+2)
    roots=(cycles[:,None]*period+base).ravel()
    indices=(cycles[:,None]*len(base)+np.arange(len(base))).ravel()
    tones=[(carrier,record['carrier_v'])]+list(record['input_tones'])
    def evaluate(t,derivative=False):
        u=np.remainder(t,period);out=np.zeros_like(u)
        for f,v in tones:
            w=2*np.pi*f
            out+=(-v.real*np.sin(w*u)-v.imag*np.cos(w*u))*w if derivative else v.real*np.cos(w*u)-v.imag*np.sin(w*u)
        return out if derivative else out-record['threshold_v']
    width=1/(32*carrier)
    curvature=sum(abs(v)*(2*np.pi*f)**2 for f,v in tones)
    load_slope=max(abs(np.diff(voltage)/np.diff(times)))
    # Repeated roots differ only by the small load perturbation. Expand
    # about their accepted periodic roots, with an explicit Taylor remainder;
    # verify final roots against the original full harmonic sum below.
    degree=12;which=np.tile(np.arange(len(base)),len(cycles))
    coefficients=np.zeros((degree+1,len(base)))
    for frequency,phasor in tones:
        term=phasor*np.exp(2j*np.pi*frequency*np.remainder(base,period))
        for order in range(degree+1):
            coefficients[order]+=term.real
            term=term*(2j*np.pi*frequency*width)/(order+1)
    coefficients[0]-=record['threshold_v']
    remainder=sum(abs(v)*(2*np.pi*f*width)**(degree+1)/math.factorial(degree+1) for f,v in tones)
    use_expansion=remainder<=1e-9
    def local(t,derivative=False):
        if not use_expansion:return evaluate(t,derivative)
        delta=(t-roots)/width;out=np.zeros_like(delta)
        for order in range(degree,0 if derivative else -1,-1):
            out=out*delta+coefficients[order,which]*(order if derivative else 1)
        return out/width if derivative else out
    minimum_slope=float(min(coefficients[1]/width)-curvature*width-load_slope)
    if minimum_slope<=0:raise ValueError('Cannot certify a monotonic local threshold bracket')
    def residual(t):return local(t)+np.interp(t,times,voltage,left=quiet_voltage,right=quiet_voltage)
    low=roots-width;high=roots+width
    if np.any(residual(low)>=-(remainder if use_expansion else 0)) or np.any(residual(high)<=(remainder if use_expansion else 0)):
        raise ValueError('Load perturbation leaves the accepted threshold bracket')
    updated=roots.copy()
    for _ in range(8):
        value=residual(updated)
        high=np.where(value>=0,updated,high);low=np.where(value<0,updated,low)
        candidate=updated-value/local(updated,True)
        updated=np.clip(candidate,low,high)
    voltage_residual=float(max(abs(evaluate(updated)+np.interp(updated,times,voltage,left=quiet_voltage,right=quiet_voltage))))
    if voltage_residual>1e-7:raise ValueError('Loaded threshold root did not converge')
    downstream=np.zeros_like(updated)
    for f,v in record['downstream_delay_tones']:
        phase=2*np.pi*f*np.remainder(updated,period)
        downstream+=v.real*np.cos(phase)-v.imag*np.sin(phase)
    output=updated+downstream+np.interp(updated,times,delay,left=quiet_delay,right=quiet_delay)
    if np.any(np.diff(output)<=0):raise ValueError('Load reverses output edge order')
    edge_record=dict(edges_s=output,indices=indices)
    if background:
        edge_record['background_periodic_clock']=dict(carrier_hz=carrier,period_s=period,
            edges_s=output[:len(base)]-cycles[0]*period)
    return edge_record,dict(edge_count=len(output),local_polynomial_degree=degree if use_expansion else None,local_polynomial_remainder_bound_v=remainder,
        maximum_input_shift_s=float(max(abs(updated-roots))),maximum_root_residual_v=voltage_residual,
        minimum_bracket_slope_v_per_s=minimum_slope,
        scope='Unique ordered local root continuations; extra crossings outside the brackets are not independently excluded.')


class LoadedEdgePhase:
    """Finite perturbed edge interval, with the periodic clock outside it."""
    def __init__(self,periodic,record):
        self.base=PeriodicEdgePhase(record['background_periodic_clock']) if 'background_periodic_clock' in record else periodic
        periodic=self.base;self.carrier=periodic.carrier
        self.edges=np.asarray(record['edges_s']);self.indices=np.asarray(record['indices'])
        self.minimum_rate_ratio=min(periodic.minimum_rate_ratio,1/(self.carrier*max(np.diff(self.edges))))
        self.phase_bound=max(periodic.phase_bound,float(max(abs(2*np.pi*(self.indices-self.carrier*self.edges)))))
        self.maximum_offset_hz=periodic.maximum_offset_hz

    def phase(self,times):
        t=np.asarray(times);base=self.base.phase(t)
        inside=(t>=self.edges[0])&(t<=self.edges[-1])
        phase=2*np.pi*(np.interp(t,self.edges,self.indices)-self.carrier*t)
        return np.where(inside,phase,base)


class DeliveredClock:
    """Optional physical edge record, assigned phase noise and local-load delay."""
    def __init__(self,environment):
        # Copy only clock inputs, not unrelated RF captures or supply traces.
        # Rebuild the clock when a feedback iteration supplies a new trajectory.
        fields=('carrier_hz','delivered_phase_tones','periodic_clock',
                'reference_threshold','design_provenance','resolved_configuration',
                'scenario_overrides','scenario_assumptions','operating_conditions')
        captured={key:environment[key] for key in fields if key in environment}
        if 'local_load_response' in environment:
            response=environment['local_load_response']
            captured['local_load_response']={key:response[key] for key in
                ('times_s','input_v','delay_s','resolved_offset_hz','background') if key in response}
        self._environment=deepcopy(captured)
        environment=self._environment
        self.coupled_load='input_v' in environment.get('local_load_response',{})
        if self.coupled_load and 'reference_threshold' not in environment:
            raise ValueError('Coupled load input voltage requires threshold-event migration before use as a delivered clock')
        self.source=PhaseNoise(tuple(environment['delivered_phase_tones']))
        self.edge_phase=PeriodicEdgePhase(environment['periodic_clock']) if 'periodic_clock' in environment else None
        if self.coupled_load:
            edges,self.load_edge_report=coupled_load_clock_edges(environment,environment['local_load_response'])
            self.edge_phase=LoadedEdgePhase(self.edge_phase,edges)
        self.maximum_offset_hz=max(self.source.maximum_offset_hz,
            0. if self.edge_phase is None else self.edge_phase.maximum_offset_hz,
            environment.get('local_load_response',{}).get('resolved_offset_hz',0.))

    @property
    def environment(self):
        """Detached clock-input snapshot; inspect without mutating clock history."""
        return deepcopy(self._environment)

    def phase(self,times):
        return self.source.phase(times)+(0. if self.edge_phase is None else self.edge_phase.phase(times))-(0. if self.coupled_load else 2*math.pi*self._environment['carrier_hz']*load_value(self._environment,times,'delay_s'))

    def crossing_error(self,ideal,carrier):
        if self.edge_phase is not None:
            if abs(carrier-self.edge_phase.carrier)>1e-6:raise ValueError('Edge clock carrier ownership mismatch')
            response=None if self.coupled_load else self._environment.get('local_load_response')
            slope=0. if response is None else max(abs(np.diff(response['delay_s'])/np.diff(response['times_s'])))
            phase_slope=sum(abs(a)*f/carrier for f,a,_ in self.source.tones)
            if phase_slope+slope>=self.edge_phase.minimum_rate_ratio:
                raise ValueError('Additional phase/load perturbation can reverse edge-clock phase')
            bound=(self.edge_phase.phase_bound+sum(abs(a) for _,a,_ in self.source.tones))/(2*np.pi*carrier)
            if response is not None:bound+=max(abs(np.asarray(response['delay_s'])))
            times=np.asarray(ideal,float);lo=np.full_like(times,-bound-1e-15);hi=-lo
            for _ in range(42):
                mid=(lo+hi)/2;positive=mid+self.phase(times+mid)/(2*np.pi*carrier)>=0
                hi=np.where(positive,mid,hi);lo=np.where(positive,lo,mid)
            error=(lo+hi)/2
            if np.any(abs(error+self.phase(times+error)/(2*np.pi*carrier))>1e-16):
                raise ValueError('Edge-clock crossing did not converge')
            return error
        if 'local_load_response' not in self._environment:
            return self.source.crossing_error(ideal,carrier)
        response=self._environment['local_load_response']
        slope=max(abs(np.diff(response['delay_s'])/np.diff(response['times_s'])))
        if slope+sum(abs(a)*f/carrier for f,a,_ in self.source.tones)>=.5:
            raise ValueError('Local-load timing violates the contractive crossing condition')
        error=-self.phase(ideal)/(2*math.pi*carrier)
        for _ in range(40):error=-self.phase(ideal+error)/(2*math.pi*carrier)
        if np.any(abs(error+self.phase(ideal+error)/(2*math.pi*carrier))>1e-16):
            raise ValueError('Local-load clock crossing did not converge')
        return error


def he_source(*, oversample, symbols=12, seed=431):
    """Band-limited OFDM symbols at an independent 20 MHz source clock."""
    w = he20(np.random.default_rng(seed).integers(0, 2, 234*symbols), gi_us=.8)
    cp = w.metadata['cp']; frames = np.asarray(w.samples).reshape(-1, 256+cp)
    spectrum = np.fft.fft(frames[:, cp:], axis=1)
    padded = np.zeros((len(frames), 256*oversample), complex)
    padded[:, :128] = spectrum[:, :128]; padded[:, -128:] = spectrum[:, -128:]
    high = np.fft.ifft(padded, axis=1)*oversample
    drive = np.concatenate([np.r_[row[-cp*oversample:], row] for row in high])
    return w, drive


def he_observation(wave, observed, *, training_symbols=2, diagnostic_training=None):
    """Known initial DATA training, pilot-only phase correction, held-out data.

    diagnostic_training substitutes a separately captured training interval for
    attribution only. It is not available to the operational receiver and never
    replaces the held-out payload or its pilot observations.
    """
    cp = wave.metadata['cp']; n = 256+cp
    original = np.asarray(wave.samples).reshape(-1, n)
    frames = np.asarray(observed).reshape(original.shape)
    x = np.fft.fft(original[:, cp:], axis=1)
    y = np.fft.fft(frames[:, cp:], axis=1)
    training_y=y
    if diagnostic_training is not None:
        training_frames=np.asarray(diagnostic_training).reshape(original.shape)
        training_y=np.fft.fft(training_frames[:,cp:],axis=1)
    data = np.asarray(wave.metadata['data']) % 256
    pilots = np.asarray(wave.metadata['pilots']) % 256
    # Least-squares frequency response uses only the declared training interval.
    h = np.sum(x[:training_symbols].conj()*training_y[:training_symbols], axis=0)
    denominator = np.sum(abs(x[:training_symbols])**2, axis=0)
    occupied = np.r_[data, pilots]
    h[occupied] /= denominator[occupied]
    if np.any(abs(h[occupied]) < 1e-15):
        raise ValueError('Training has no observable occupied-tone gain')
    corrected = y[training_symbols:, data]/h[data]
    pilot_observations = y[training_symbols:, pilots]/h[pilots]
    # Fixture pilot polarity is constant +1, known independently of payload.
    phase = np.angle(np.sum(pilot_observations, axis=1))
    corrected *= np.exp(-1j*phase[:, None])
    expected = x[training_symbols:, data]
    error_energy=np.sum(abs(corrected-expected)**2,axis=0)
    worst=int(np.argmax(error_energy))
    return dict(evm_rms=float(np.sqrt(np.mean(abs(corrected-expected)**2)/np.mean(abs(expected)**2))),
        training_min_to_median_gain=float(min(abs(h[data]))/np.median(abs(h[data]))),
        worst_error_subcarrier=int((data[worst]+128)%256-128),
        worst_subcarrier_error_energy_fraction=float(error_energy[worst]/max(float(sum(error_energy)),1e-300)),
        bpsk_errors=int(np.sum((corrected.real > 0) != (expected.real > 0))),
        evaluated_bits=int(expected.size),known_data_training_symbols=training_symbols,
        pilot_phase_correction=True,real_preamble_acquisition=False,
        diagnostic_external_training=diagnostic_training is not None)


def he_scalar_observation(wave,observed,*,observer_cutoff_hz,training_symbols=2):
    """Diagnostic TX error with one training-fit gain and delay, no channel EQ."""
    from scipy.optimize import minimize_scalar
    cp=wave.metadata['cp'];n=256+cp
    original=np.asarray(wave.samples).reshape(-1,n)
    frames=np.asarray(observed).reshape(original.shape)
    if not 0<training_symbols<len(frames):raise ValueError('Held-out TX symbols required')
    bins=np.r_[np.asarray(wave.metadata['data']),np.asarray(wave.metadata['pilots'])]%256
    frequency=((bins+128)%256-128)*20e6/256
    x=np.fft.fft(original[:,cp:],axis=1)[:,bins]
    y=np.fft.fft(frames[:,cp:],axis=1)[:,bins]
    # De-embed only the independently known diagnostic instrument, never a
    # transfer fitted from this transmitter's per-tone response.
    b,a=_analog_prototype('rx_all_pole_control')
    instrument=np.polyval(b,1j*frequency/observer_cutoff_hz)/np.polyval(a,1j*frequency/observer_cutoff_hz)
    y=y/instrument
    train=x[:training_symbols]
    def fit(delay_s):
        shifted=y[:training_symbols]*np.exp(2j*np.pi*frequency*delay_s)
        gain=np.vdot(train,shifted)/np.vdot(train,train)
        residual=float(np.mean(abs(shifted-gain*train)**2))
        return residual,gain
    grid=np.linspace(-.4e-6,.4e-6,161)
    best=int(np.argmin([fit(t)[0] for t in grid]))
    low=grid[max(0,best-1)];high=grid[min(len(grid)-1,best+1)]
    optimized=minimize_scalar(lambda ns:fit(ns*1e-9)[0],bounds=(low*1e9,high*1e9),method='bounded',options={'xatol':1e-7})
    delay=optimized.x*1e-9;_,gain=fit(delay)
    if abs(gain)<1e-15:raise ValueError('Unobservable TX scalar gain')
    corrected=y[training_symbols:]*np.exp(2j*np.pi*frequency*delay)/gain
    expected=x[training_symbols:]
    return dict(evm_rms=float(np.sqrt(np.mean(abs(corrected-expected)**2)/np.mean(abs(expected)**2))),
        fitted_delay_s=float(delay),fitted_gain_magnitude=float(abs(gain)),evaluated_symbols=len(expected),
        training_symbols=training_symbols,per_tone_equalization=False,
        scope='Known DATA training fits only one complex scalar and delay; remaining symbols held out. De-embeds the analytic diagnostic observer response only. No transmitter per-tone or per-symbol correction, no actual HE preamble or standards EVM procedure. Finite-grid instrument and boundary errors remain.')


def minimum_envelope_oversample(environment, *, sample_hz=20e6, guard_hz=None):
    """Power-of-two Nyquist floor for retained clock/rail tones, not convergence proof."""
    if not math.isfinite(sample_hz) or sample_hz<=0:raise ValueError('Positive envelope sample rate required')
    if guard_hz is None:guard_hz=max(12e6,environment['carrier_hz']/64)
    if not math.isfinite(guard_hz) or guard_hz<0:raise ValueError('Nonnegative spectral guard required')
    offset=max(DeliveredClock(environment).maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))
    return 2**max(2,math.floor(math.log2(max(1.,2*(offset+guard_hz)/sample_hz)))+1)


def receive_supply_reference(environment, key):
    parameters=environment.get('rf_receive_supply_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound RF receive model missing supply references')
        return 3.3
    value=parameters[key]
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError('Positive finite RF receive supply reference required')
    return value


def receive_gain_elasticity(environment):
    """Shared required rail-to-gain transfer; unbound fixtures retain unity."""
    parameters=environment.get('rf_receive_supply_parameters')
    if parameters is None:
        receive_supply_reference(environment,'gain_reference_v')
        return 1.
    value=parameters['gain_supply_elasticity']
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
        raise ValueError('Nonnegative finite RF gain supply elasticity required')
    return value


def receive_supply_gain(rails,gain_reference_v,gain_supply_elasticity):
    """Assigned broadband gain regulation, independent of rail headroom."""
    rails=np.asarray(rails,float)
    if not np.all(np.isfinite(rails)) or not math.isfinite(gain_reference_v) or gain_reference_v<=0:
        raise ValueError('Finite RF rail and positive gain reference required')
    if isinstance(gain_supply_elasticity,bool) or not math.isfinite(gain_supply_elasticity) or gain_supply_elasticity<0:
        raise ValueError('Nonnegative finite RF gain supply elasticity required')
    gain_scale=1+gain_supply_elasticity*(rails/gain_reference_v-1)
    if np.any(rails<=0) or np.any(gain_scale<=0):
        raise ValueError('Positive RF rail and gain multiplier required')
    return gain_scale


def receive_frontend(drive, times, rails, lo_phase, *, sample_hz,
                     wanted_dbm=-85., blocker_dbm=-30., noise_rng=None,
                     blocker_offset_hz=12e6, blocker_envelope=None, external_loss_db=2.,
                     noise_figure_db=6., input_iip3_dbm=0., temperature_k=300.15,early_gain_db=20.,gain_reference_v=3.3,gain_supply_elasticity=1.):
    """Shared antenna-to-filter forcing; caller owns time, rails, LO and RNG.

    No local clock realization or record-local noise reset. The returned complex
    envelope uses the existing 2 dB external loss, 6 dB NF, 0 dBm IIP3 and
    configured rail-sensitive early gain assumptions. Filtering and conversion belong
    to the caller so their state can survive transport and mode boundaries.
    """
    if not math.isfinite(gain_reference_v) or gain_reference_v<=0:raise ValueError('Positive gain reference required')
    if not math.isfinite(early_gain_db):raise ValueError('Finite early gain required')
    drive=np.asarray(drive,complex);times=np.asarray(times,float)
    rails=np.asarray(rails,float);lo_phase=np.asarray(lo_phase,float)
    if (drive.ndim!=1 or not len(drive) or
            any(v.shape!=drive.shape for v in (times,rails,lo_phase)) or
            any(not np.all(np.isfinite(v)) for v in (drive,times,rails,lo_phase)) or
            not math.isfinite(sample_hz) or sample_hz<=0):
        raise ValueError('Finite aligned RF forcing and positive sample rate required')
    if not math.isfinite(temperature_k) or temperature_k<=0:
        raise ValueError('Positive finite physical temperature required')
    if not math.isfinite(external_loss_db) or external_loss_db<0:raise ValueError('External insertion loss')
    mixed=math.sqrt(100*1e-3*10**((wanted_dbm-external_loss_db)/10))*drive
    if blocker_dbm is not None:
        envelope=np.ones(len(times),complex) if blocker_envelope is None else np.asarray(blocker_envelope,complex)
        if envelope.shape!=times.shape or not np.all(np.isfinite(envelope)) or not math.isfinite(blocker_offset_hz):
            raise ValueError('Finite aligned blocker envelope and offset required')
        # Caller owns continuous-time alignment and unit average-power normalization.
        mixed+=math.sqrt(100*1e-3*10**((blocker_dbm-external_loss_db)/10))*envelope*np.exp(2j*math.pi*blocker_offset_hz*times)
    if not math.isfinite(noise_figure_db) or noise_figure_db<0 or not math.isfinite(input_iip3_dbm):
        raise ValueError('Finite nonnegative NF and finite IIP3 required')
    mixed,nonlinear=third_order_frontend(mixed,input_iip3_dbm)
    if noise_rng is not None:
        sigma=math.sqrt(50*1.380649e-23*temperature_k*10**(noise_figure_db/10)*sample_hz)
        # Interleaved I/Q draws preserve the same physical noise sequence when
        # transport divides one continuous record into different chunks.
        draws=noise_rng.normal(size=(len(times),2))
        mixed+=sigma*(draws[:,0]+1j*draws[:,1])
    gain_scale=receive_supply_gain(rails,gain_reference_v,gain_supply_elasticity)
    return mixed*(10**(early_gain_db/20)*gain_scale)*np.exp(-1j*lo_phase),nonlinear


def settling_gain(times, target_db, *, initial_db=None, tau_s=0., command_s=0.):
    """Assigned first-order voltage-gain response to an external numeric command.

    No packet truth or decoded quality selects the gain. This models settling,
    not autonomous AGC or the command transport latency.
    """
    initial_db=target_db if initial_db is None else initial_db
    if not all(math.isfinite(v) for v in (target_db,initial_db,tau_s,command_s)) or tau_s<0 or command_s<0:
        raise ValueError('Finite gain command and nonnegative timing required')
    times=np.asarray(times,float)
    if not np.all(np.isfinite(times)):raise ValueError('Finite gain observation times required')
    initial=10**(initial_db/20);target=10**(target_db/20)
    age=np.maximum(times-command_s,0.)
    fraction=np.where(times>=command_s,1.,0.) if tau_s==0 else -np.expm1(-age/tau_s)
    return initial+(target-initial)*fraction


def clock_supply_sensitivity(environment):
    """Resolve magnitude from explicit scenario or the shared clock requirement."""
    config=environment.get('clock_input_configuration')
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if config is None and bound:
        raise ValueError('Design-bound clock requires supply delay parameters')
    nominal=.1 if config is None else config['supply_sensitivity_ps_per_mv']
    value=environment.get('local_supply_sensitivity_ps_per_mv',nominal)
    if isinstance(value,bool) or not np.isfinite(value) or value<0:
        raise ValueError('Finite nonnegative clock supply sensitivity required')
    return value


def clock_supply_delay_pole(environment):
    """Shared clock-input pole, with a fallback only for primitive fixtures."""
    config=environment.get('clock_input_configuration')
    if config is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound clock requires supply delay parameters')
        return 1e9
    pole=config['supply_delay_pole_hz']
    if isinstance(pole,bool) or not np.isfinite(pole) or pole<=0:
        raise ValueError('Positive finite clock supply delay pole required')
    return pole


def reference_acceptance_parameters(environment):
    parameters=environment.get('reference_acceptance_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound reference requires acceptance parameters')
        return dict(threshold_v=.020,effective_peak_limit_v=.6,leg_peak_limit_v=.6)
    if not isinstance(parameters,dict) or set(parameters)!={'threshold_v','effective_peak_limit_v','leg_peak_limit_v'}:
        raise ValueError('Complete reference input acceptance parameters required')
    for key,value in parameters.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (key!='threshold_v' and value<=0):
            raise ValueError('Invalid reference input acceptance parameter: '+key)
    if abs(parameters['threshold_v'])>=parameters['effective_peak_limit_v']:
        raise ValueError('Reference threshold must lie inside effective input envelope')
    return dict(parameters)


def reference_supply_parameters(environment):
    """Resolve shared reference rejection; defaults only for independent primitives."""
    parameters=environment.get('reference_supply_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound reference requires supply coupling parameters')
        parameters=dict(supply_fraction_per_v=.1,supply_pole_hz=10e6)
    return parameters


def reference_supply_transfer(environment, frequency_hz):
    """Fractional reference motion per rail volt."""
    parameters=reference_supply_parameters(environment)
    return parameters['supply_fraction_per_v']/(1+1j*np.asarray(frequency_hz)/parameters['supply_pole_hz'])


def selected_tx_filter(environment):
    """Return a supported paired reconstruction prototype from the snapshot."""
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if not bound:
        return 'tx_third_order',3
    pair=[environment['filter_parameters']['txfilter_'+lane] for lane in ('i','q')]
    orders={item['order'] for item in pair}
    if len(orders)!=1 or any(item['gain']!=1. for item in pair):
        raise ValueError('Matched unity-gain TX reconstruction required')
    order=pair[0]['order']
    if order==3 and all(item.get('default_q')==1. for item in pair):
        return 'tx_third_order',3
    if order==5 and all(item.get('default_response')=='Butterworth' and
            len(item.get('stage_q',[]))==2 and
            all(math.isclose(q,want,rel_tol=1e-9) for q,want in zip(item['stage_q'],(.6180339887498948,1.618033988749895)))
            for item in pair):
        return 'rx_all_pole_control',5
    raise ValueError('Unsupported TX reconstruction prototype')


def selected_filter_cutoff(environment, direction, requested, primitive_default):
    """Resolve the paired hardware range; primitive examples remain independent."""
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if not bound:
        cutoff=primitive_default if requested is None else requested
    else:
        parameters=environment['filter_parameters']
        pair=[parameters[direction+'filter_'+lane] for lane in ('i','q')]
        expected_order=5 if direction=='rx' else selected_tx_filter(environment)[1]
        if any(item['order']!=expected_order for item in pair):
            raise ValueError('Unsupported paired '+direction+' filter order')
        # This adapter implements fixed normalized prototypes, not arbitrary
        # coefficient programming. Reject changed shapes instead of ignoring them.
        if direction=='rx' and any(item['default_response']!='elliptic 1 dB ripple 36.4078 dB stop attenuation' for item in pair):
            raise ValueError('Unsupported RX default response prototype')
        low=max(item['cutoff_hz'][0] for item in pair)
        high=min(item['cutoff_hz'][1] for item in pair)
        if low>high:
            raise ValueError('Paired filter cutoff ranges do not overlap')
        cutoff=high if requested is None else requested
        if isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not low<=cutoff<=high:
            raise ValueError('Filter cutoff outside shared paired '+direction+' range')
    if isinstance(cutoff,bool) or not math.isfinite(cutoff) or cutoff<=0:
        raise ValueError('Positive finite filter cutoff required')
    return cutoff


def validate_rf_configuration_identity(environment):
    """Reject mixing snapshots even when their mode and rates happen to agree."""
    config=environment.get('resolved_configuration')
    if config is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Shared-design RF path requires a resolved configuration')
        return
    provenance=environment.get('design_provenance')
    if not isinstance(provenance,dict) or not provenance:
        raise ValueError('Configured RF environment requires design provenance')
    if any(config.get(key)!=value for key,value in provenance.items()):
        raise ValueError('RF configuration conflicts with environment design provenance')
    if config.get('engine')!='rf':
        raise ValueError('RF path requires a resolved RF engine configuration')
    from design_definition import validate_transport_binding
    validate_transport_binding(environment)


def wideband_receive(environment, *, oversample=128, wanted_dbm=-85., blocker_dbm=-30.,
                     noise=True, family='rx_finite_zero', gain_settings_db=None,
                     sar_parameters=None,load_capture=None,disabled_noise_sources=(),adc_enob=None,filter_interpolation='zoh',observation_capture=None,
                     filter_integrator_ratio=None,filter_retune_ratio=None,comparator_model=None,gain_codes_db=None,
                     noise_figure_db=None,input_iip3_dbm=None,gain_initial_db=None,gain_tau_s=None,gain_command_s=0.,
                     gain_hypothesis_reason=None,diagnostic_reason=None,aperture_rms_s=None,cutoff_hz=None):
    """Absolute RF -> nonlinear frontend -> loaded LO -> filter -> native ADC.

    Gain sweep is a requirement search, NOT an AGC. All cases carry the same
    received waveform; gain is never selected from held-out decoding results.
    """
    validate_rf_configuration_identity(environment)
    cutoff=selected_filter_cutoff(environment,'rx',cutoff_hz,
        9.53125e6 if family=='rx_finite_zero' else 9.157407e6)
    from converter_dynamics import validate_sar_binding
    validate_sar_binding(environment,sar_parameters,comparator_model=comparator_model)
    config=environment.get('resolved_configuration')
    inventory=environment.get('receiver_parameters')
    pga_peak=receiver_pga_peak(environment)
    lna_gain=receiver_lna_gain(environment)
    if 'design_provenance' in environment and inventory is None:
        raise ValueError('Design-bound receiver requires snapshot gain parameters')
    if inventory is not None:
        for lane in ('adc_i','adc_q'):
            if (inventory[lane]['native_bits'],inventory[lane]['transport_bits'])!=(10,12):
                raise ValueError('This RX adapter requires native 10-bit and transport 12-bit words')
        if sar_parameters is None and inventory['adc_i']['enob_target']!=inventory['adc_q']['enob_target']:
            raise ValueError('Assigned-ENOB RX adapter requires matched I/Q ENOB targets')
    defaults=(dict(noise_figure_db=6.,input_iip3_dbm=0.,adc_enob=8.) if inventory is None else
        dict(noise_figure_db=inventory['lna']['noise_figure_db'],input_iip3_dbm=inventory['lna']['iip3_dbm'],
             adc_enob=inventory['adc_i']['enob_target']))
    defaults['aperture_rms_s']=environment['adc_noise_parameters']['aperture_rms_s'] if inventory is not None else 10e-12
    supplied=dict(aperture_rms_s=aperture_rms_s,noise_figure_db=noise_figure_db,input_iip3_dbm=input_iip3_dbm,adc_enob=adc_enob)
    diagnostic_overrides={key:dict(selected=defaults[key],diagnostic=value) for key,value in supplied.items()
        if value is not None and value!=defaults[key]}
    gain_response=receiver_pga_response(environment) if inventory is not None else 0.
    if gain_tau_s is not None and gain_tau_s!=gain_response:
        diagnostic_overrides['gain_tau_s']=dict(selected=gain_response,diagnostic=gain_tau_s)
    if diagnostic_overrides and inventory is not None:
        if not isinstance(diagnostic_reason,str) or not diagnostic_reason.strip():
            raise ValueError('Receiver parameter override requires an explicit diagnostic reason')
        for change in diagnostic_overrides.values():
            change['reason']=diagnostic_reason.strip()
    gain_tau_s=gain_response if gain_tau_s is None else gain_tau_s
    if isinstance(gain_tau_s,bool) or not math.isfinite(gain_tau_s) or gain_tau_s<0:
        raise ValueError('Finite nonnegative gain response required')
    aperture_rms_s=defaults['aperture_rms_s'] if aperture_rms_s is None else aperture_rms_s
    if not math.isfinite(aperture_rms_s) or aperture_rms_s<0:raise ValueError('Nonnegative finite ADC aperture required')
    noise_figure_db=defaults['noise_figure_db'] if noise_figure_db is None else noise_figure_db
    input_iip3_dbm=defaults['input_iip3_dbm'] if input_iip3_dbm is None else input_iip3_dbm
    adc_enob=defaults['adc_enob'] if adc_enob is None else adc_enob
    supported=None if inventory is None else set(inventory['pga_i']['gain_db']) & set(inventory['pga_q']['gain_db'])
    if gain_settings_db is None:
        gain_settings_db=((config['pga_gain_db'],) if config is not None else
                          (max(supported),) if supported is not None else (42.,48.,54.,60.))
    gains=tuple(gain_settings_db)
    if not gains or any(not math.isfinite(gain) for gain in gains):
        raise ValueError('Finite nonempty gain settings required')
    assessed=gains+(() if gain_initial_db is None else (gain_initial_db,))
    if any(not math.isfinite(gain) for gain in assessed):
        raise ValueError('Finite initial and target gains required')
    unsupported=[] if supported is None else sorted({gain for gain in assessed if gain not in supported})
    if config is not None and unsupported:
        raise ValueError('Unsupported gain cannot be a resolved hardware setting')
    if unsupported and (not isinstance(gain_hypothesis_reason,str) or not gain_hypothesis_reason.strip()):
        raise ValueError('Unsupported gain requires an explicit hypothetical-gain reason')
    gain_settings_db=gains
    if comparator_model is not None and sar_parameters is None:
        raise ValueError('Comparator timing requires causal SAR')
    if gain_codes_db is not None and (any(gain not in gain_codes_db for gain in gain_settings_db) or
            (gain_initial_db is not None and gain_initial_db not in gain_codes_db)):
        raise ValueError('Requested PGA gain is outside the selected inventory')
    if type(oversample) is not int or oversample < 4:
        raise ValueError('Integer envelope oversampling required')
    if not set(disabled_noise_sources)<={'thermal','converter','aperture'}:
        raise ValueError('Known receiver noise sources required')
    enabled={name:bool(noise and name not in disabled_noise_sources) for name in ('thermal','converter','aperture')}
    if sar_parameters is not None and supplied['adc_enob'] is not None and supplied['adc_enob']!=defaults['adc_enob']:
        raise ValueError('Assigned ENOB override is not a causal SAR model parameter')
    wave, drive = he_source(oversample=oversample)
    mix_hz = 20e6*oversample; lo = environment['carrier_hz']
    config=environment.get('resolved_configuration')
    if config is not None:
        if config['engine']!='rf' or config['direction']!='rx' or config['reference_hz']!=lo:
            raise ValueError('Receiver configuration does not match electrical environment')
        if tuple(gain_settings_db)!=(config['pga_gain_db'],):
            raise ValueError('Gain sweep conflicts with resolved receive configuration')
        adc_hz=config['sample_hz']
    else:
        adc_hz=lo/64
    phase = DeliveredClock(environment)
    if max(phase.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+12e6 >= mix_hz/2:
        raise ValueError('Resolve LO sidebands before analog filtering')
    # Include a leading settling interval and trailing FPGA FIR lookahead.
    lead = round(2e-6*mix_hz); tail = round(2e-6*mix_hz)
    drive = np.r_[np.zeros(lead), drive, np.zeros(tail)]
    times = np.arange(len(drive))/mix_hz
    rails = rail_at(environment, times)
    temperature_k=(sar_parameters.temperature_k if sar_parameters is not None else
                   environment['converter_parameters']['temperature_k'] if 'design_provenance' in environment else 300.15)
    mixed,nonlinear=receive_frontend(drive,times,rails,phase.phase(times),
        sample_hz=mix_hz,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,
        noise_figure_db=noise_figure_db,input_iip3_dbm=input_iip3_dbm,
        noise_rng=np.random.default_rng(901) if enabled['thermal'] else None,temperature_k=temperature_k,early_gain_db=lna_gain,
        gain_reference_v=receive_supply_reference(environment,'gain_reference_v'),
        gain_supply_elasticity=receive_gain_elasticity(environment))
    filtered = analog_filter(mixed, mix_hz, family=family, cutoff_hz=cutoff,interpolation=filter_interpolation,
        integrator_ratio=filter_integrator_ratio,retune_ratio=filter_retune_ratio)
    ideal = np.arange(1, math.floor(times[-1]*adc_hz)+1)/adc_hz
    actual = ideal+phase.crossing_error(ideal, lo)
    if enabled['aperture']:
        actual += np.random.default_rng(1801).normal(0, aperture_rms_s, len(actual))
    if np.any(np.diff(actual) <= 0):
        raise ValueError('Nonmonotonic converter timestamps')
    # Exact ZOH updates return the analog state at the END of each substep.
    filter_times = times+(1/mix_hz if filter_interpolation=='zoh' else 0.)
    sampled = np.interp(actual, filter_times, filtered.real)+1j*np.interp(actual, filter_times, filtered.imag)
    reference = reference_at(environment, actual)
    headroom = pga_peak*rail_at(environment, actual)/receive_supply_reference(environment,'headroom_reference_v')
    observer_times = 2e-6+np.arange(len(wave.samples))/20e6
    rows = []
    for gain_db in gain_settings_db:
        before_clip = sampled*settling_gain(actual,gain_db,initial_db=gain_initial_db,tau_s=gain_tau_s,command_s=gain_command_s)
        clipped = (abs(before_clip.real) > headroom) | (abs(before_clip.imag) > headroom)
        limited = np.clip(before_clip.real, -headroom, headroom)+1j*np.clip(before_clip.imag, -headroom, headroom)
        if sar_parameters is None:
            words, conversion = native_adc(limited, reference, noise=enabled['converter'],enob=adc_enob)
        else:
            from converter_dynamics import paired_sar
            beginning=actual-sar_parameters.acquisition_s
            start=(np.interp(beginning,filter_times,filtered.real)+1j*np.interp(beginning,filter_times,filtered.imag))*settling_gain(beginning,gain_db,initial_db=gain_initial_db,tau_s=gain_tau_s,command_s=gain_command_s)
            initial_headroom=pga_peak*rail_at(environment,beginning)/receive_supply_reference(environment,'headroom_reference_v')
            start=np.clip(start.real,-initial_headroom,initial_headroom)+1j*np.clip(start.imag,-initial_headroom,initial_headroom)
            rail_sampler,reference_sampler=prepared_supply_functions(environment)
            words,conversion,trace=paired_sar(limited,start,actual,
                reference_sampler,rail_sampler,
                parameters=sar_parameters,noise=enabled['converter'],comparator_model=comparator_model)
            if load_capture is not None:
                if len(gain_settings_db)!=1:raise ValueError('Choose one gain before recording its load trajectory')
                load_capture.update(trace)
        normalized = (words[:, 0]+1j*words[:, 1])/2048
        # FPGA sees nominal timestamps, never the actual clock errors/reference.
        observed = bandlimited_samples(normalized, observer_times*adc_hz-1, 32, cutoff=20e6/adc_hz)
        if observation_capture is not None:
            if len(gain_settings_db)!=1:raise ValueError('Choose one gain for observation capture')
            observation_capture.update(wave=wave,observed=observed)
        payload = (ideal >= 2e-6) & (ideal < 2e-6+len(wave.samples)/20e6)
        rows.append(dict(pga_gain_db=gain_db,gain_supported_by_design=None if supported is None else gain_db in supported,
            pga_clipped_samples=int(clipped.sum()),
            pga_clipped_samples_during_source=int(clipped[payload].sum()),
            adc=conversion,observation=he_observation(wave, observed)))
    return dict(**{key:deepcopy(environment[key]) for key in ('diagnostic_input_intervention','diagnostic_input_reason') if key in environment},
        design_provenance=deepcopy(environment.get('design_provenance')),resolved_configuration=deepcopy(config),
        scenario_overrides=deepcopy(environment.get('scenario_overrides',[])),
        scenario_assumptions=deepcopy(environment.get('scenario_assumptions',{})),
        operating_conditions=deepcopy(environment.get('operating_conditions')),
        pga_nominal_peak_limit_v=pga_peak,gain_hypothesis_reason=gain_hypothesis_reason,unsupported_gain_settings_db=unsupported,
        receiver_diagnostic_overrides=diagnostic_overrides,
        result_role=('independent_primitive' if inventory is None else
            'hypothetical_gain_experiment' if unsupported else
            'receiver_parameter_diagnostic' if diagnostic_overrides else 'design_gain_settings'),
        wanted_antenna_dbm=wanted_dbm,blocker_antenna_dbm=blocker_dbm,
        blocker_offset_hz=12e6,external_loss_db=2.,external_selective_rejection_db=0.,
        chip_input_noise_figure_db=noise_figure_db,early_voltage_gain_db=lna_gain,input_iip3_dbm=input_iip3_dbm,
        thermal_noise_temperature_k=temperature_k,
        frontend_nonlinearity=nonlinear,filter_family=family,cutoff_hz=cutoff,
        filter_integrator_ratio=filter_integrator_ratio,filter_retune_ratio=filter_retune_ratio,
        native_bits=10,enob_hypothesis=adc_enob if sar_parameters is None else None,
        converter_model='assigned_enob' if sar_parameters is None else 'closed_loop_sar_requirement',
        comparator_model=comparator_model,gain_codes_db=gain_codes_db,
        gain_transition=dict(initial_db=gain_initial_db,tau_s=gain_tau_s,command_s=gain_command_s),
        aperture_rms_s=aperture_rms_s,adc_hz=adc_hz,
        mixer_hz=mix_hz,oversample=oversample,filter_interpolation=filter_interpolation,noise_enabled=any(enabled.values()),noise_sources=enabled,
        coupled_load_clock=getattr(phase,'load_edge_report',None),
        observed_rail_interval_v=[float(rails.min()),float(rails.max())],
        reference_interval_v=[float(reference.min()),float(reference.max())],
        resampler_taps=64,fpga_resampler_lookahead_s=32/adc_hz,
        gain_cases=rows,complete=False,
        scope=('Shared loaded source/input/supply spectrum and environment-owned mode budget. Assigned instantaneous early-gain rail sensitivity; fixed NF/IIP3 and ideal linear filter internals. '+
            ('ADC transfer is native 10-bit with assigned excess noise; no SAR/reference-load settling or mismatch. ' if sar_parameters is None else
             'ADC uses causal trial decisions, limited reference recovery and finite acquisition/DAC settling; pole/current/noise hypotheses are unqualified, with no mismatch; optional comparator regeneration remains an assigned requirement model. ')+
            'Known DATA training/ideal boundaries, no real preamble, CFO search, AGC or packet/PER qualification. Finite RF record does not qualify emissions or continuous host service.'))


def driver_wake_response(environment, *, released_current_a, wake_start_s,
                         ramp_s=20e-9, grid_s=1e-9, duration_s=12e-6,reference_input=None,guard_s=8e-6):
    """Return from a settled reduced driver load to the budgeted warm load.

    The full 28 mA is ALREADY in the environment's DC ledger. The incremental
    current starts negative and returns to zero; it is never added a second time.
    This is a bounded wake sensitivity, not a prediction of transistor current.
    """
    from robustness_envelope import local_load_state_space
    from converter_dynamics import supply_delay_gain,reference_load_parameters
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if bound:
        required=('local_supply_sensitivity_ps_per_mv','local_supply_delay_sign','reference_load_parameters','transmitter_parameters')
        missing=[key for key in required if key not in environment]
        if missing:raise ValueError('Design-bound driver wake missing parameters: '+', '.join(missing))
        if reference_input is not None and reference_input!=environment['reference_load_parameters']:
            raise ValueError('Driver wake reference input conflicts with design-bound environment')
    if bound:
        reference_input=reference_load_parameters(environment)
    elif reference_input is None:
        reference_input=environment.get('reference_load_parameters')
    delay_gain=supply_delay_gain(clock_supply_sensitivity(environment),environment.get('local_supply_delay_sign',1.))
    bias=(environment['transmitter_parameters']['rfdriver']['bias_current_a']
          if bound else .028)
    if not 0 <= released_current_a <= bias or ramp_s <= 0 or grid_s <= 0:
        raise ValueError('Wake must stay within the driver current reservation')
    beginning=-2e-6
    if wake_start_s < beginning or wake_start_s+ramp_s >= duration_s:
        raise ValueError('Wake ramp must fit inside the recorded trajectory')
    relative=np.arange(round((duration_s-beginning)/grid_s)+1)*grid_s
    times=relative+beginning
    if reference_input is not None:
        from converter_dynamics import coupled_reference_load_transfer
        if not math.isfinite(guard_s) or guard_s<=0:raise ValueError('Positive finite settling guard required')
        guard=math.ceil(guard_s/grid_s)
        size=2**math.ceil(math.log2(len(times)+2*guard))
        extended=times[0]+(np.arange(size)-guard)*grid_s
        delta=-released_current_a*(1-np.clip((extended-wake_start_s)/ramp_s,0.,1.))
        frequencies=np.fft.rfftfreq(size,grid_s);spectrum=np.fft.rfft(delta)
        ports=coupled_reference_load_transfer(frequencies,environment['network'],**reference_input)
        def transformed(transfer):return np.fft.irfft(spectrum*transfer,n=size)[guard:guard+len(times)]
        rail=transformed(ports['rail_v_per_a'])
        delay=transformed(ports['rail_v_per_a']*delay_gain/(1+1j*frequencies/clock_supply_delay_pole(environment)))
        reference=transformed(ports['rail_v_per_a']*reference_supply_transfer(environment,frequencies))
        input_v=transformed(ports['input_v_per_a'])
        load=bias-released_current_a*(1-np.clip((times-wake_start_s)/ramp_s,0.,1.))
        dc= float(-released_current_a*ports['rail_v_per_a'][0].real)
        if abs(rail[0]-dc)>1e-6 or abs(rail[-1])>1e-6:
            raise ValueError('Extend coupled wake guards/record to reach settled endpoints')
        result=dict(times_s=times,rail_v=rail,delay_s=delay,reference_fraction=reference,
            input_v=input_v,resolved_offset_hz=.5/grid_s,driver_current_a=load)
        leg_report={}
        if 'input_leg_v_per_a' in ports:
            result['input_leg_v']=np.fft.irfft(spectrum[:,None]*ports['input_leg_v_per_a'],n=size,axis=0)[guard:guard+len(times)]
            leg_report['input_leg_voltage_abs_peak_v']=np.max(abs(result['input_leg_v']),axis=0).tolist()
        return result,dict(**leg_report,released_current_a=released_current_a,wake_start_s=wake_start_s,
            ramp_s=ramp_s,grid_s=grid_s,guard_s=guard_s,coupled_reference_input=reference_input,
            driver_current_interval_a=[float(min(load)),float(max(load))],
            initial_rail_relief_v=dc,initial_settling_error_v=float(rail[0]-dc),
            rail_perturbation_interval_v=[float(min(rail)),float(max(rail))],
            input_voltage_abs_peak_v=float(max(abs(input_v))),final_rail_delta_v=float(rail[-1]),
            final_current_delta_a=float(load[-1]-bias),peak_clock_shift_s=float(max(abs(delay))),
            scope='Negative incremental driver current returns to its already-budgeted 28 mA; no extra DC load. Coupled tied-return PDN and REF_IN source impedance are retained. Guarded periodic FFT approximation with settled endpoint checks; input voltage requires threshold-event solving. Grid and guard controls remain necessary, not physical wake or bias-readiness qualification.')
    # Bin-average slope integrates the linear current ramp exactly, including
    # boundaries not aligned to the numerical grid.
    increment=released_current_a*np.clip((times-wake_start_s)/ramp_s,0,1)
    slope=np.r_[np.diff(increment)/grid_s,0.]
    system=local_load_state_space(environment['network'])
    initial=np.zeros(5);initial[4]=-released_current_a
    initial[:4]=np.linalg.solve(system.A[:4,:4],-system.A[:4,4]*initial[4])
    _,rail,state=signal.lsim(system,U=slope,T=relative,X0=initial,interp=False)
    initial_rail=float((system.C@initial).item())
    def filtered(pole_hz,scale):
        pole=2*np.pi*pole_hz
        return signal.lsim(signal.StateSpace([[-pole]],[[pole]],[[scale]],[[0.]]),
            U=rail,T=relative,X0=[initial_rail],interp=True)[1]
    load=bias+state[:,4]
    if max(abs(state[-1]))>1e-9:
        raise ValueError('Extend the wake record: passive state has not settled')
    result=dict(times_s=times,rail_v=rail,delay_s=filtered(clock_supply_delay_pole(environment),delay_gain),
        reference_fraction=filtered(reference_supply_parameters(environment)['supply_pole_hz'],
            reference_supply_parameters(environment)['supply_fraction_per_v']),resolved_offset_hz=.5/grid_s,
        driver_current_a=load)
    report=dict(released_current_a=released_current_a,wake_start_s=wake_start_s,
        ramp_s=ramp_s,grid_s=grid_s,driver_current_interval_a=[float(min(load)),float(max(load))],
        initial_rail_relief_v=initial_rail,rail_perturbation_interval_v=[float(min(rail)),float(max(rail))],
        final_current_delta_a=float(state[-1,4]),final_rail_delta_v=float(rail[-1]),
        peak_clock_shift_s=float(max(abs(result['delay_s']))),
        scope='Settled reduced-bias start, continuous passive PDN state and finite current ramp back to the already-budgeted 28 mA. No additional DC load. Assigned delay/reference sensitivities; no signal-dependent RF-cycle current, bias readiness, DAC glitches or substrate coupling.')
    return result,report


def supply_blocker_requirement(*,carrier_hz,ripple_hz,ripple_peak_v,mean_rail_v,
        sensitivity_s_per_v,delay_pole_hz,blocker_over_wanted_db,allocation=.05):
    """First-sideband requirement at a blocker offset that folds into passband.

    Separate PM and AM terms; their deterministic phases are coherent, so do
    not RSS them or identify either as the sole cause of an integrated result.
    Allocation is a diagnostic branch allowance, not a protocol EVM threshold.
    """
    from scipy.special import jv
    from scipy.optimize import brentq
    positive=(carrier_hz,ripple_hz,ripple_peak_v,mean_rail_v,sensitivity_s_per_v,delay_pole_hz,allocation)
    if not all(math.isfinite(x) and x>0 for x in positive) or not math.isfinite(blocker_over_wanted_db):
        raise ValueError('Finite positive requirement inputs required')
    ratio=10**(blocker_over_wanted_db/20)
    delay_gain=sensitivity_s_per_v/math.sqrt(1+(ripple_hz/delay_pole_hz)**2)
    phase_peak=2*math.pi*carrier_hz*ripple_peak_v*delay_gain
    if phase_peak>=1:raise ValueError('Use a full sideband model beyond small modulation')
    pm=ratio*abs(float(jv(1,phase_peak)))
    am=ratio*ripple_peak_v/(2*mean_rail_v)
    phase_limit=brentq(lambda phase:ratio*jv(1,phase)-allocation,0.,1.)
    pm_ripple_limit=phase_limit/(2*math.pi*carrier_hz*delay_gain)
    am_ripple_limit=2*mean_rail_v*allocation/ratio
    return dict(phase_peak_rad=phase_peak,delay_peak_s=ripple_peak_v*delay_gain,
        blocker_pm_sideband_to_wanted_amplitude=pm,
        blocker_am_sideband_to_wanted_amplitude=am,
        first_order_coherent_am_pm_interval=[abs(pm-am),pm+am],
        diagnostic_branch_allocation=allocation,pm_only_ripple_limit_v=pm_ripple_limit,
        am_only_ripple_limit_v=am_ripple_limit,
        conservative_combined_small_signal_ripple_limit_v=allocation/(ratio*(math.pi*carrier_hz*delay_gain+1/(2*mean_rail_v))),
        pm_only_additional_preselection_db=max(0.,20*math.log10(pm/allocation)),
        combined_first_order_additional_preselection_db=max(0.,20*math.log10((pm+am)/allocation)),
        am_floor_exceeds_allocation_with_ideal_clock=am>allocation,
        minimum_am_rejection_db_with_ideal_clock=max(0.,20*math.log10(am/allocation)),
        maximum_delay_sensitivity_s_per_v_at_present_ripple=(
            max(0.,allocation-am)/(ratio*math.pi*carrier_hz*ripple_peak_v)
            *math.sqrt(1+(ripple_hz/delay_pole_hz)**2)),
        mitigation_decision=('Clock-only improvement cannot meet this branch allocation: '
            'gain-path AM already exceeds it. Reduce shared ripple or reject the blocker '
            'before mixing; clock improvement can complement either.' if am>allocation else
            'Clock-only reduction may fit this branch allocation; remaining impairment '
            'and resource budgets still require joined verification.'),
        scope='One translated blocker sideband, assumed unity relative in-band response. PM uses exact J1; AM is the selected linear gain law. The coherent interval omits AM/PM product and higher sidebands, filtering/equalization, noise and nonlinearities. Limits are inverse requirements, not guarantees or measured rejection. Preselection must act before mixing.')



def passive_supply_isolation_requirement(*, frequency_hz, input_ripple_v,
        output_ripple_v, load_current_a, capacitance_f, input_min_v, load_min_v):
    """Optimistic single-pole RC necessary bound, excluding parasitics/load AC."""
    values=(frequency_hz,input_ripple_v,output_ripple_v,load_current_a,
            capacitance_f,input_min_v,load_min_v)
    if not all(math.isfinite(v) and v>0 for v in values):
        raise ValueError('Finite positive RC budget inputs required')
    if input_min_v<=load_min_v or output_ripple_v>=input_ripple_v:
        raise ValueError('Positive dropout and attenuation requirements required')
    omega=2*math.pi*frequency_hz
    rc=math.sqrt((input_ripple_v/output_ripple_v)**2-1)/omega
    required_r=rc/capacitance_f
    allowed_r=(input_min_v-load_min_v)/load_current_a
    return dict(required_rc_s=rc,required_series_resistance_ohm=required_r,
        resulting_dc_drop_v=required_r*load_current_a,
        maximum_series_resistance_from_dc_ohm=allowed_r,
        minimum_capacitance_from_dc_f=rc/allowed_r,
        fits_optimistic_rc_and_dc=required_r<=allowed_r,
        scope='Ideal one-pole upstream-ripple attenuation with constant load. '
        'No ESL, ESR, load-generated noise, shared return, regulator or stability model. '
        'Failure rejects this RC allocation; success cannot qualify a physical supply.')


def tx_gain_reference(driver_parameters, value):
    """A supplied driver owns its gain law; bare primitives retain a default."""
    if driver_parameters is not None:
        owned=driver_parameters['gain_reference_v']
        if value is not None and value!=owned:
            raise ValueError('TX gain reference conflicts with supplied driver')
        value=owned
    elif value is None:
        value=3.3
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError('Positive finite TX gain reference required')
    return value


def tx_amplitude_bound(requirement, *, gain_reference_v=None,nominal_gain=4.5,driver_parameters=None,output_parameters=None,reconstruction_family="tx_third_order"):
    """Conservative gain/headroom bound, without claiming waveform quality."""
    gain_reference_v=tx_gain_reference(driver_parameters,gain_reference_v)
    model=(dict(dc_elasticity=1.,high_frequency_elasticity=1.,pole_hz=1.)
           if driver_parameters is None else driver_parameters['supply_gain_model'])
    dc=model['dc_elasticity'];floor=model['high_frequency_elasticity'];pole=model['pole_hz']
    if any(isinstance(v,bool) or not math.isfinite(v) for v in (dc,floor,pole)) or not 0<=floor<=dc or pole<=0:
        raise ValueError('Finite passive first-order TX supply-gain response required')
    output=dict(TX_PARAMETERS if output_parameters is None else output_parameters)
    driver=(dict(bias_current_a=.028,source_r_ohm_differential=40.,load_ohm_differential=50.,
                 headroom_per_rail_v=.3) if driver_parameters is None else driver_parameters)
    headroom=2*driver['headroom_per_rail_v']
    current_limit=driver['bias_current_a']*(driver['source_r_ohm_differential']+driver['load_ohm_differential'])
    peak=requirement['reconstructed_complex_peak_v']
    low,high=requirement['supply_interval_v'];reference=requirement['reference_max_v']
    g=10**(output['gain_imbalance_db']/40)
    phase=math.radians(output['phase_error_deg'])
    matrix=np.array([[g,-math.sin(phase)/g],[0,math.cos(phase)/g]])
    gain=float(np.linalg.norm(matrix,2));before_compression=gain*peak+abs(output['lo_feedthrough'])
    if output['cubic']*before_compression**2>=1/3:
        raise ValueError('Amplitude contract exceeds monotonic output-stage model')
    # Compression can only reduce magnitude within the declared valid domain.
    if 1+dc*(low/gain_reference_v-1)<=0:
        raise ValueError('Amplitude interval leaves positive supply-gain domain')
    # Positive one-pole kernel keeps its retained state inside the entire past
    # input interval. Charge the largest permissible past rail at each current
    # rail; dynamic gain need not drop immediately when headroom drops.
    def maximum_gain(v):
        return 1+floor*(v/gain_reference_v-1)+(dc-floor)*(high/gain_reference_v-1)
    opened=nominal_gain*maximum_gain(high)*before_compression
    allowed=min(low-headroom,current_limit)
    same_rail=[dict(rail_v=v,open_peak_bound_v=nominal_gain*maximum_gain(v)*before_compression,
        allowed_open_peak_v=min(v-headroom,current_limit)) for v in (low,high)]
    same_rail_margin=min(row['allowed_open_peak_v']-row['open_peak_bound_v'] for row in same_rail)
    residues,poles=analog_modes(reconstruction_family)
    l1=float(np.sum(abs(residues)/(-poles.real)))
    return dict(gain_reference_v=gain_reference_v,driver_parameters=dict(driver),output_parameters=output,open_peak_bound_v=opened,allowed_open_peak_v=allowed,
        within_declared_headroom=opened<=allowed,iq_operator_gain_bound=gain,
        correlated_supply_bound=dict(endpoints=same_rail,minimum_margin_v=same_rail_margin,
            within_declared_headroom=same_rail_margin>=0,
            proof="At each instantaneous rail, bound retained low-pass gain state by the maximum past rail. This is valid only when the initial state and entire rail history stay in the declared interval. The resulting gain bound is affine in current rail; subtracting it from the minimum voltage/current limit is concave piecewise affine, so endpoints suffice. Includes supply-gain memory, not cold startup, out-of-range prehistory or a waveform-amplitude proof."),
        reconstruction_family=reconstruction_family,reconstruction_l1_upper_bound=l1,
        sufficient_native_complex_code_radius=int(math.floor(peak/(reference*l1)*512)),
        scope='Worst supply gain versus minimum rail headroom; triangle bound on the full stable filter impulse response. Native code radius includes both I and Q jointly and must hold for all retained history. Conservative sufficient alternative, not maximum usable power or an ENOB/EVM guarantee.')


def tx_power_requirement(*, mean_load_power_w, crest_factor_db, minimum_supply_v,
                         source_resistance_ohm=40., load_resistance_ohm=50.,
                         peak_current_limit_a=.028, headroom_per_rail_v=.3):
    """Necessary port headroom, not a sufficient distortion/drive certificate."""
    values=(mean_load_power_w, minimum_supply_v, source_resistance_ohm,
            load_resistance_ohm, peak_current_limit_a)
    if not all(math.isfinite(x) and x>0 for x in values) or not math.isfinite(crest_factor_db) or crest_factor_db<0 or not math.isfinite(headroom_per_rail_v) or headroom_per_rail_v<0:
        raise ValueError('Positive finite power/port parameters and nonnegative crest/headroom required')
    crest=10**(crest_factor_db/10)
    current=math.sqrt(2*mean_load_power_w*crest/load_resistance_ohm)
    opened=current*(source_resistance_ohm+load_resistance_ohm)
    allowed=min(max(0.,minimum_supply_v-2*headroom_per_rail_v),
                peak_current_limit_a*(source_resistance_ohm+load_resistance_ohm))
    ceiling=(allowed/(source_resistance_ohm+load_resistance_ohm))**2*load_resistance_ohm/(2*crest)
    return dict(required_peak_load_current_a=current,required_open_peak_v=opened,
        minimum_supply_from_headroom_v=opened+2*headroom_per_rail_v,
        necessary_port_bounds_pass=opened<=allowed,
        ideal_headroom_mean_power_ceiling_w=ceiling,
        scope='Necessary differential resistive-port voltage/current bound only. Assumed crest factor must be rechecked after distortion. Excludes converter/reconstruction amplitude, emissions, noise, reactive loading, loss and physical driver feasibility.')



def tx_spectral_diagnostic(envelope, sample_hz):
    """Relative baseband-band powers, not a protocol emission mask."""
    x=np.asarray(envelope,complex)
    if x.ndim!=1 or len(x)<16 or not np.all(np.isfinite(x)) or sample_hz<=80e6:
        raise ValueError('Finite resolved complex capture required')
    spectrum=np.abs(np.fft.fft(x*np.hanning(len(x))))**2
    frequency=np.fft.fftfreq(len(x),1/sample_hz)
    bands={'wanted':(-10e6,10e6),'lower_adjacent':(-30e6,-10e6),
           'upper_adjacent':(10e6,30e6)}
    power={name:float(sum(spectrum[(frequency>=lo)&(frequency<hi)]))
           for name,(lo,hi) in bands.items()}
    if power['wanted']<=0:raise ValueError('Nonzero wanted-band energy required')
    return dict(bands_hz={k:list(v) for k,v in bands.items()},
        relative_band_power_db={k:float(10*np.log10(max(v,1e-300)/power['wanted'])) for k,v in power.items()},
        bin_spacing_hz=sample_hz/len(x),samples=len(x),window='Hann',
        scope='Finite DATA-window complex-envelope band-power diagnostic before observer filtering. Adjacent bands are illustrative 20 MHz bands, not standard mask/ACLR acceptance. Excludes packet switching, external RF filtering, RF harmonics and frequencies outside sampled envelope. No absolute-power estimate from windowed FFT.')


def relative_burst_mask_screen(envelope,sample_hz,mask,*,maximum_offset_hz=39e6):
    """Untapered finite-record energy diagnostic, never standards acceptance.

    Gaussian RBW smoothing is applied to power, not amplitude. Fourfold FFT
    padding samples the finite-burst spectrum between original DFT bins; it
    does not create observation duration or implement a VBW detector.
    """
    from scipy.fft import next_fast_len
    x=np.asarray(envelope,complex)
    offsets=np.asarray(mask['relative_mask_offset_hz'],float)
    levels=np.asarray(mask['relative_mask_db'],float)
    rbw=mask['rbw_hz']
    if x.ndim!=1 or len(x)<16 or not np.all(np.isfinite(x)) or not np.any(abs(x)>0):
        raise ValueError('Nonzero finite complete record required for burst spectrum')
    if offsets.ndim!=1 or len(offsets)<2 or levels.shape!=offsets.shape or not np.all(np.isfinite(offsets)) or not np.all(np.isfinite(levels)) or offsets[0]<=0 or np.any(np.diff(offsets)<=0):
        raise ValueError('Finite ordered mask offsets and matching levels required')
    if not all(np.isfinite(v) and v>0 for v in (sample_hz,rbw,maximum_offset_hz)) or maximum_offset_hz<offsets[-1] or maximum_offset_hz+6*rbw>=sample_hz/2:
        raise ValueError('Resolve the mask span and RBW away from Nyquist')
    count=next_fast_len(4*len(x))
    frequency=np.fft.fftshift(np.fft.fftfreq(count,1/sample_hz))
    energy=abs(np.fft.fftshift(np.fft.fft(x,n=count)))**2
    df=sample_hz/count
    sigma=rbw/(2*np.sqrt(2*np.log(2))*df)
    radius=int(4*sigma+.5)
    grid=np.arange(-radius,radius+1,dtype=float)
    kernel=np.exp(-.5*(grid/sigma)**2);kernel/=sum(kernel)
    density=np.maximum(signal.fftconvolve(energy,kernel,mode='same'),0.)
    reference=float(max(density[abs(frequency)<=offsets[0]]))
    if reference<=0:raise ValueError('Nonzero in-band spectral-density reference required')
    relative=10*np.log10(np.maximum(density,1e-300)/reference)
    limit=np.interp(abs(frequency),offsets,levels)
    evaluated=(abs(frequency)>=offsets[0])&(abs(frequency)<=maximum_offset_hz)
    excess=np.where(evaluated,relative-limit,-np.inf);worst=int(np.argmax(excess))
    return dict(worst_relative_excess_db=float(excess[worst]),
        worst_offset_hz=float(frequency[worst]),rbw_hz=rbw,
        record_duration_s=len(x)/sample_hz,fft_bin_spacing_hz=df,
        observation_resolution_hz=sample_hz/len(x),window='none',
        maximum_offset_hz=maximum_offset_hz,
        rbw_grid_resolved=bool(df<=rbw/4),
        relative_energy_screen_pass=bool(excess[worst]<=0) if df<=rbw/4 else None,
        qualification=False,mask_pass=None,
        scope='Whole supplied record with zero outside it, no taper or active-window slicing. Maximum in-band smoothed spectral density is the relative reference. Gaussian power-spectrum smoothing only: no time-domain detector/VBW, absolute/regulatory limit, complete-PPDU validation, switching model or harmonics outside the envelope. Padding improves interpolation, not observation duration. A passing energy screen is not spectral-mask acceptance.')


def rf_pad_transfer(frequency_hz, *, driver_r_ohm, pad_series_ohm,
                    bond_series_ohm, bond_loop_h, differential_cap_f, load_ohm=50.,series_match_f=None):
    """Differential lumped ladder: source R -> pad C -> bond R/L -> load.

    Inputs are differential equivalents; two equal shunt-to-ground pad
    capacitances become C_leg/2. Signal-loop L is not supply-return L.
    Frequency-domain linear requirements only, with no ESD or distributed line.
    """
    frequency=np.asarray(frequency_hz,float)
    if not np.all(np.isfinite(frequency)) or np.any(frequency<0):
        raise ValueError('Finite nonnegative physical RF frequencies required')
    values=(driver_r_ohm,pad_series_ohm,bond_series_ohm,bond_loop_h,differential_cap_f,load_ohm)
    if not all(math.isfinite(v) and v>=0 for v in values) or min(driver_r_ohm,load_ohm)<=0:
        raise ValueError('Passive RF pad/load values required')
    s=2j*np.pi*frequency
    source=driver_r_ohm+pad_series_ohm
    branch=load_ohm+bond_series_ohm+s*bond_loop_h
    if series_match_f is not None and (not math.isfinite(series_match_f) or series_match_f<=0):
        raise ValueError('Positive finite external matching capacitance required')
    branch_y=1/branch if series_match_f is None else s*series_match_f/(1+s*series_match_f*branch)
    pad_y=s*differential_cap_f+branch_y
    pad_voltage=1/(1+source*pad_y)
    return dict(load_voltage=load_ohm*pad_voltage*branch_y,
                pad_voltage=pad_voltage,
                driver_current=pad_voltage*pad_y,
                load_current=pad_voltage*branch_y)



def rf_pad_waveform(opened, sample_hz, carrier_hz, *, driver_r_ohm,
                    pad_series_ohm,bond_series_ohm,bond_loop_h,differential_cap_f,
                    load_ohm=50.,series_match_f=None,initial_state=None):
    """Causal complex-envelope RLC state, exact for each held envelope interval.

    Physical state is pad volts, bond current scaled by branch resistance,
    and optional series-capacitor volts. No circular FFT or future waveform.
    Outputs are interval-end samples; returned state can continue another chunk.
    """
    rf_pad_transfer(carrier_hz,driver_r_ohm=driver_r_ohm,pad_series_ohm=pad_series_ohm,
        bond_series_ohm=bond_series_ohm,bond_loop_h=bond_loop_h,
        differential_cap_f=differential_cap_f,load_ohm=load_ohm,series_match_f=series_match_f)
    source=np.asarray(opened,complex)
    if (source.ndim!=1 or not len(source) or not np.all(np.isfinite(source)) or
            not math.isfinite(sample_hz) or sample_hz<=0 or min(bond_loop_h,differential_cap_f)<=0):
        raise ValueError('Finite waveform, positive rate and nonzero physical L/C required')
    rs=driver_r_ohm+pad_series_ohm;rb=load_ohm+bond_series_ohm
    dimension=2 if series_match_f is None else 3
    a=np.zeros((dimension,dimension),complex)
    a[0,0]=-1/(rs*differential_cap_f);a[0,1]=-1/(rb*differential_cap_f)
    a[1,0]=rb/bond_loop_h;a[1,1]=-rb/bond_loop_h
    if series_match_f is not None:
        a[1,2]=-rb/bond_loop_h;a[2,1]=1/(rb*series_match_f)
    a-=2j*np.pi*carrier_hz*np.eye(dimension)
    b=np.zeros(dimension);b[0]=1/(rs*differential_cap_f)
    identity=(sample_hz,carrier_hz,driver_r_ohm,pad_series_ohm,bond_series_ohm,
              bond_loop_h,differential_cap_f,load_ohm,series_match_f)
    state=np.zeros(dimension,complex)
    if initial_state is not None:
        if tuple(initial_state['configuration'])!=identity:raise ValueError('Compatible retained RF pad state required')
        state=np.array([complex(*value) for value in initial_state['state']])
        if state.shape!=(dimension,) or not np.all(np.isfinite(state)):raise ValueError('Finite retained RF pad state required')
    poles,vectors=np.linalg.eig(a);inverse=np.linalg.inv(vectors)
    forcing=inverse@b;modal=inverse@state
    outputs=np.zeros((dimension,len(source)),complex)
    for k,pole in enumerate(poles):
        decay=np.exp(pole/sample_hz)
        gain=np.expm1(pole/sample_hz)/pole*forcing[k]
        values,_=signal.lfilter([gain],[1,-decay],source,zi=[decay*modal[k]])
        outputs+=vectors[:,k,None]*values
    current=outputs[1]/rb
    before=np.r_[state[0],outputs[0,:-1]]
    return dict(load_voltage=load_ohm*current,pad_voltage=outputs[0],
        driver_current=(source-outputs[0])/rs,
        driver_current_at_interval_start=(source-before)/rs,
        load_current=current,series_cap_voltage=None if dimension==2 else outputs[2],
        final_state=dict(configuration=list(identity),state=[[float(z.real),float(z.imag)] for z in outputs[:,-1]]))


def tx_supply_gain(rails,reference_v,driver_parameters=None,times=None,*,state=None):
    """Held-input response with optional persistent state across caller chunks.

    An empty state starts settled to the first rail. Between observations the
    previous input is held, including gaps; callers must supply quiet-period rail
    changes too. This does not model cold bias startup or unobserved rail motion.
    State is committed only after validation and a positive-gain result.
    """
    rails=np.asarray(rails,float)
    if rails.ndim!=1 or not len(rails) or not np.all(np.isfinite(rails)):
        raise ValueError('Nonempty finite TX rail trajectory required')
    if isinstance(reference_v,bool) or not math.isfinite(reference_v) or reference_v<=0:
        raise ValueError('Positive finite TX gain reference required')
    if state is not None and not isinstance(state,dict):
        raise ValueError('TX supply-gain state must be a dictionary')
    model=(dict(dc_elasticity=1.,high_frequency_elasticity=1.,pole_hz=1.)
           if driver_parameters is None else driver_parameters['supply_gain_model'])
    dc=model['dc_elasticity'];floor=model['high_frequency_elasticity'];pole=model['pole_hz']
    if any(isinstance(v,bool) or not math.isfinite(v) for v in (dc,floor,pole)) or not 0<=floor<=dc or pole<=0:
        raise ValueError('Finite passive first-order TX supply-gain response required')
    identity=[reference_v,dc,floor,pole]
    x=rails/reference_v-1.
    if times is None and state is None and np.all(rails==rails[0]):
        # A constant-rail static call explicitly uses settled prehistory.
        # Varying rails or retained state still require causal timestamps.
        result=1+dc*x
        if np.any(result<=0):raise ValueError('TX supply-gain model outside positive gain range')
        return rails/reference_v if dc==1. else result
    if dc!=floor or state is not None:
        times=np.asarray(times,float)
        if times.shape!=rails.shape or not np.all(np.isfinite(times)) or np.any(np.diff(times)<=0):
            raise ValueError('Ordered TX times required for dynamic supply-gain response')
    if state:
        if state.get('configuration')!=identity:
            raise ValueError('TX supply-gain state belongs to a different configuration')
        previous_time=state['time_s'];previous_input=state['held_fractional_input']
        previous_filtered=state['filtered_fractional_input']
        if not all(math.isfinite(v) for v in (previous_time,previous_input,previous_filtered)) or times[0]<=previous_time:
            raise ValueError('TX supply-gain continuation must advance finite retained state')
    else:
        previous_filtered=x[0]
    if dc==floor:
        filtered=x
    else:
        filtered=np.empty_like(x)
        if state:
            decay=math.exp(-2*math.pi*pole*(times[0]-previous_time))
            filtered[0]=decay*previous_filtered+(1-decay)*previous_input
        else:
            filtered[0]=previous_filtered
        for i in range(1,len(x)):
            decay=math.exp(-2*math.pi*pole*(times[i]-times[i-1]))
            filtered[i]=decay*filtered[i-1]+(1-decay)*x[i-1]
    result=rails/reference_v if dc==floor==1. else 1+floor*x+(dc-floor)*filtered
    if not np.all(np.isfinite(result)) or np.any(result<=0):
        raise ValueError('TX supply-gain model outside positive gain range')
    if state is not None:
        state.update(configuration=identity,time_s=float(times[-1]),
            held_fractional_input=float(x[-1]),filtered_fractional_input=float(filtered[-1]))
    return result


def transmit_output(reconstructed, rails, lo_phase, *, available_current_a=None, nominal_gain=4.5,pad_series_ohm=0.,
                    driver_parameters=None,rail_bias_a=.044,output_parameters=None,gain_reference_v=None,times=None,supply_gain_state=None):
    """Shared mixer/driver/port; caller owns DAC history, supply and LO phase.

    The 28 mA driver is already included in the 44 mA RF allocation. These are
    assigned distortion/impedance/compliance requirements, not transistor proof.
    """
    gain_reference_v=tx_gain_reference(driver_parameters,gain_reference_v)
    reconstructed=np.asarray(reconstructed,complex);rails=np.asarray(rails,float)
    lo_phase=np.asarray(lo_phase,float)
    if (reconstructed.ndim!=1 or not len(reconstructed) or
            rails.shape!=reconstructed.shape or lo_phase.shape!=reconstructed.shape or
            any(not np.all(np.isfinite(v)) for v in (reconstructed,rails,lo_phase))):
        raise ValueError('Finite aligned TX signal, rails and phase required')
    driver=(dict(bias_current_a=.028,source_r_ohm_differential=40.,load_ohm_differential=50.,
                 headroom_per_rail_v=.3) if driver_parameters is None else driver_parameters)
    bias=driver['bias_current_a'];load_r=driver['load_ohm_differential']
    available=np.full(len(rails),bias) if available_current_a is None else np.asarray(available_current_a,float)
    if available.shape!=rails.shape or not np.all(np.isfinite(available)) or np.any(available<0):
        raise ValueError('Finite nonnegative driver-current trajectory required')
    if not math.isfinite(nominal_gain) or nominal_gain<=0:raise ValueError("Positive finite gain required")
    gain_state=None if supply_gain_state is None else dict(supply_gain_state)
    opened=nominal_gain*tx_supply_gain(rails,gain_reference_v,driver_parameters,times,state=gain_state)*output_envelope(reconstructed,np.exp(1j*lo_phase),**(TX_PARAMETERS if output_parameters is None else output_parameters))
    if not math.isfinite(pad_series_ohm) or pad_series_ohm<0:
        raise ValueError('Finite nonnegative differential pad series resistance required')
    source_resistance=driver['source_r_ohm_differential']+pad_series_ohm
    limit=available*(source_resistance+load_r);clipped=abs(opened)>limit
    opened*=np.minimum(1.,limit/np.maximum(abs(opened),1e-30))
    port=rf_tx_resistive_port(opened,source_resistance_ohm=source_resistance,load_resistance_ohm=load_r)
    electrical=rf_tx_compliance_budget(peak_open_v=float(max(abs(opened))),
        minimum_supply_v=float(min(rails)),total_rail_bias_a=rail_bias_a,
        source_resistance_ohm=source_resistance,load_resistance_ohm=load_r,driver_bias_current_a=bias,
        peak_current_limit_a=bias,headroom_per_rail_v=driver['headroom_per_rail_v'],differential=True)
    if supply_gain_state is not None:
        supply_gain_state.update(gain_state)
    return port,electrical,clipped


def configured_tx_gain(environment, supplied=None):
    """Use and validate the shared TX codebook, never a parallel gain setting."""
    from design_definition import resolve_tx_gain
    config=environment['resolved_configuration']
    driver=environment['transmitter_parameters']['rfdriver']
    if any(key not in config for key in ('tx_gain','tx_gain_code','resolved_tx_gain')):
        raise ValueError('Resolved TX gain and code are required')
    code,gain=resolve_tx_gain(driver,config['tx_gain'])
    if type(config['tx_gain_code']) is not int or config['tx_gain_code']!=code or config['resolved_tx_gain']!=gain:
        raise ValueError('TX gain code conflicts with shared driver parameters')
    if supplied is not None and (isinstance(supplied,bool) or supplied!=gain):
        raise ValueError('TX gain conflicts with resolved configuration')
    return gain


def fpga_tx_filter_correction(samples,*,sample_hz,filter_family,cutoff_hz,taps=49,coefficient_fraction_bits=12):
    """Causal FPGA-owned FIR for a prepared record with explicit zero history.

    The caller owns guard samples, launch time, amplitude and record abort/reset.
    No normalization, time advance, clipping or extra on-chip state is applied.
    """
    from rf_filter_tradeoff import tx_preemphasis_coefficients
    samples=np.asarray(samples,complex)
    if samples.ndim!=1 or not len(samples) or not np.all(np.isfinite(samples)):
        raise ValueError('Finite nonempty FPGA TX record required')
    coefficients,delay_samples,fit_error=tx_preemphasis_coefficients(
        filter_family=filter_family,cutoff_hz=cutoff_hz,taps=taps,
        coefficient_fraction_bits=coefficient_fraction_bits,sample_hz=sample_hz,include_resampler=False)
    corrected=signal.lfilter(coefficients,[1.],samples)
    metadata=dict(taps=len(coefficients),coefficient_fraction_bits=coefficient_fraction_bits,
        coefficients=coefficients.tolist(),alignment_delay_s=delay_samples/sample_hz,
        history_samples=len(coefficients)-1,fit_maximum_error=fit_error,
        arithmetic='floating-point accumulation with quantized coefficients; FPGA wordlength unqualified',
        scope='Causal FPGA FIR before native DAC quantization; zero initial record history. No time advance or gain renormalization. Fits assigned analog filter and DAC hold only. Caller must supply guard samples and account for delay; source interpolation has separate lookahead. Record abort explicitly discards FPGA preparation, not retained chip analog state.')
    return corrected,metadata


def wideband_transmit(environment, *, oversample=128, cutoff_hz=None, noise=True,onset_capture=None,
                      input_rms_codes=None,nominal_gain=None,pad_series_ohm=0.,rf_load=None,impairment_capture=None,fpga_preemphasis=None):
    """FPGA interpolation -> native DAC -> selected reconstruction -> loaded RF.

    Uses the existing assigned TX output-stage distortion and resistive port.
    The observer has independent timing and no access to the local LO phase.
    """
    if fpga_preemphasis is None:
        fpga_preemphasis=environment.get('fpga_tx_preparation',{}).get('wideband_correction_enabled',False)
    if type(fpga_preemphasis) is not bool:raise ValueError('Explicit FPGA correction enable required')
    validate_rf_configuration_identity(environment)
    cutoff_hz=selected_filter_cutoff(environment,'tx',cutoff_hz,20e6)
    reconstruction_family,reconstruction_order=selected_tx_filter(environment)
    if type(oversample) is not int or oversample<4:
        raise ValueError('Integer envelope oversampling required')
    if type(noise) is not bool:
        raise ValueError('Explicit boolean TX noise enable required')
    if input_rms_codes is not None and (isinstance(input_rms_codes,bool) or
            not isinstance(input_rms_codes,(int,float)) or not math.isfinite(input_rms_codes) or
            not 0<input_rms_codes<=2047):
        raise ValueError('Positive finite TX RMS transport-code request required')
    lo = environment['carrier_hz']; mix_hz = 20e6*oversample
    config=environment.get('resolved_configuration')
    if config is None and (any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))):
        raise ValueError('Shared-design transmitter requires a resolved configuration')
    if config is not None:
        if config['engine']!='rf' or config['direction']!='tx' or config['reference_hz']!=lo:
            raise ValueError('Transmitter configuration does not match electrical environment')
        dac_hz=config['sample_hz']
        allocation=environment['transmitter_parameters']
        for name in ('dac_i','dac_q'):
            if (allocation[name]['native_bits'],allocation[name]['transport_bits'])!=(10,12):
                raise ValueError('This DAC adapter requires native 10-bit and transport 12-bit words')
        if allocation['dac_i']['differential_peak_v']!=allocation['dac_q']['differential_peak_v']:
            raise ValueError('Paired DAC model requires matched full-scale amplitudes')
        full_scale=allocation['dac_i']['differential_peak_v']
        enob=environment['dac_noise_parameters']['enob']
        aperture=environment['dac_noise_parameters']['aperture_rms_s']
        driver=allocation['rfdriver']
        nominal_gain=configured_tx_gain(environment,nominal_gain)
    else:
        dac_hz=lo/64
        driver=None
        full_scale=1.;enob=8.;aperture=10e-12
        if nominal_gain is None:nominal_gain=4.5
    if not 0<enob<=10 or not math.isfinite(aperture) or aperture<0 or not math.isfinite(full_scale) or full_scale<=0:
        raise ValueError('Valid DAC noise and amplitude hypotheses required')
    clock = DeliveredClock(environment)
    if max(clock.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+dac_hz >= mix_hz/2:
        raise ValueError('Resolve TX clock sidebands and first DAC image')
    wave, _ = he_source(oversample=1)
    duration = 4e-6+len(wave.samples)/20e6
    ideal = np.arange(math.ceil(duration*dac_hz)+1)/dac_hz
    edges = ideal+clock.crossing_error(ideal, lo)
    if noise:
        edges += np.random.default_rng(3101).normal(0, aperture, len(edges))
    if np.any(np.diff(edges) <= 0):
        raise ValueError('Nonmonotonic DAC timestamps')
    scale=.12 if input_rms_codes is None else input_rms_codes/(2048*math.sqrt(float(np.mean(abs(wave.samples)**2))))
    prepared = scale*bandlimited_samples(wave.samples, (ideal-2e-6)*20e6, 32)
    correction=None
    if fpga_preemphasis:
        policy=environment.get('fpga_tx_preparation',{})
        controls=({key:policy[key] for key in ('taps','coefficient_fraction_bits')}
                  if 'design_provenance' in environment else {})
        prepared,correction=fpga_tx_filter_correction(prepared,sample_hz=dac_hz,
            filter_family=reconstruction_family,cutoff_hz=cutoff_hz,**controls)
    correction_delay_s=0. if correction is None else correction['alignment_delay_s']
    raw = np.stack((np.rint(prepared.real*2048), np.rint(prepared.imag*2048)), axis=-1)
    words = np.clip(raw, -2048, 2047).astype(np.int64)
    analog, converter = native_dac(words, full_scale*reference_scale_at(environment, edges))
    if noise:
        sigma = math.sqrt((2**(2-2*enob)-(1/512)**2)/12)
        rng = np.random.default_rng(3201)
        analog += sigma*(rng.normal(size=len(edges))+1j*rng.normal(size=len(edges)))*full_scale*reference_scale_at(environment, edges)
    times = np.arange(math.ceil(duration*mix_hz))/mix_hz
    reconstructed = analog_hold_at(analog, edges, times, family=reconstruction_family, cutoff_hz=cutoff_hz)
    rf_times = times
    rails = rail_at(environment, rf_times)
    response=environment.get('local_load_response',{})
    bias=.028 if driver is None else driver['bias_current_a']
    source_r=40. if driver is None else driver['source_r_ohm_differential']
    load_r=50. if driver is None else driver['load_ohm_differential']
    available=np.full(len(times),bias)
    if 'driver_current_a' in response:
        available=np.maximum(0,np.interp(times,response['times_s'],response['driver_current_a'],
            left=response['driver_current_a'][0],right=bias))
    lo_phase=clock.phase(rf_times)
    port,electrical,clipped=transmit_output(reconstructed,rails,lo_phase,times=rf_times,
        available_current_a=available,nominal_gain=nominal_gain,pad_series_ohm=pad_series_ohm,
        gain_reference_v=driver['gain_reference_v'] if driver is not None else 3.3,
        driver_parameters=driver,rail_bias_a=environment['inventory_current_a']['rf'] if driver is not None else .044,
        output_parameters=environment['rf_output_parameters'] if driver is not None else None)
    emitted=port['envelope_v']
    if impairment_capture is not None:
        active_probe=(rf_times>=2e-6+correction_delay_s)&(rf_times<duration-2e-6+correction_delay_s)
        window_probe=np.hanning(int(np.sum(active_probe)))
        frequency_probe=abs(np.fft.fftfreq(len(window_probe),1/mix_hz))
        masks={'within_10mhz':frequency_probe<10e6,
               'offset_10_to_30mhz':(frequency_probe>=10e6)&(frequency_probe<30e6),
               'offset_30_to_50mhz':(frequency_probe>=30e6)&(frequency_probe<50e6),
               'offset_above_50mhz':frequency_probe>=50e6}
        parameters=dict(environment['rf_output_parameters'] if driver is not None else TX_PARAMETERS)
        cases=[]
        for label,probe_rails,probe_phase,probe_parameters in (
                ('all',rails,lo_phase,parameters),
                ('constant_output_rail',np.full_like(rails,float(np.mean(rails))),lo_phase,parameters),
                ('no_mixer_lo_phase',rails,np.zeros_like(lo_phase),parameters),
                ('no_output_cubic',rails,lo_phase,dict(parameters,cubic=0.)),
                ('constant_output_rail_and_no_mixer_lo_phase',np.full_like(rails,float(np.mean(rails))),np.zeros_like(lo_phase),parameters),
                ('ten_db_less_output_am_and_mixer_pm',np.mean(rails)+(rails-np.mean(rails))/math.sqrt(10),lo_phase/math.sqrt(10),parameters),
                ('twenty_db_less_output_am_and_mixer_pm',np.mean(rails)+(rails-np.mean(rails))/10,lo_phase/10,parameters)):
            probe,_,probe_clipped=transmit_output(reconstructed,probe_rails,probe_phase,times=rf_times,
                available_current_a=available,nominal_gain=nominal_gain,pad_series_ohm=pad_series_ohm,
                gain_reference_v=driver['gain_reference_v'] if driver is not None else 3.3,
                driver_parameters=driver,rail_bias_a=environment['inventory_current_a']['rf'] if driver is not None else .044,
                output_parameters=probe_parameters)
            capture_probe=probe['envelope_v'][active_probe]
            ps=abs(np.fft.fft(capture_probe*window_probe))**2/(len(capture_probe)*sum(window_probe**2)*2*load_r)
            cases.append(dict(name=label,band_power_w={name:float(sum(ps[mask])) for name,mask in masks.items()},
                clipped_samples=int(sum(probe_clipped)),
                baseline_waveform_difference_v=float(max(abs(probe['envelope_v']-emitted))) if label=='all' else None))
        impairment_capture.update(cases=cases,plane='resistive output before optional reactive RF load',
            scope='One-at-a-time interventions after identical DAC/reconstruction history; source, ADC/DAC clock timing and reference disturbances remain. Constant output rail affects only driver amplitude/compliance, not the upstream package. Finite 10/20 dB probes scale the complete output AM and mixer PM trajectories, retaining the mean output rail; they are inverse requirements, not a realizable rail filter or a selective reduction of clock supply sensitivity. DAC timing and reference histories remain unchanged. No physical design savings, additive noise decomposition or compliance claim; nonlinear/coherent interactions remain.')
    reactive_report=None
    if rf_load is not None:
        if np.any(clipped):raise ValueError('Reactive load requires nonlinear current-limit re-solve')
        opened=emitted*(source_r+load_r+pad_series_ohm)/load_r
        load_options=dict(rf_load)
        if 'load_ohm' in load_options and load_options['load_ohm']!=load_r:
            raise ValueError('Reactive load resistance conflicts with the declared driver load')
        load_options['load_ohm']=load_r
        network=rf_pad_waveform(opened,mix_hz,lo,driver_r_ohm=source_r,pad_series_ohm=pad_series_ohm,**load_options)
        peak_current=np.maximum(abs(network['driver_current']),abs(network['driver_current_at_interval_start']))
        if np.any(peak_current>available):raise ValueError('Reactive driver current exceeds assigned available bias')
        emitted=network['load_voltage']
        port['load_power_w']=abs(emitted)**2/(2*load_r)
        precheck=dict(electrical,checks=dict(electrical['checks']))
        source_power=np.maximum(.5*np.real(opened*np.conj(network['driver_current'])),
            .5*np.real(opened*np.conj(network['driver_current_at_interval_start'])))
        electrical.update(resistive_precheck=precheck,
            peak_driver_current_a=float(max(peak_current)),
            peak_load_current_a=float(max(abs(network['load_current']))),
            peak_load_power_w=float(max(port['load_power_w'])),
            peak_envelope_rf_power_w=float(max(source_power)))
        electrical['checks']['peak_current']=bool(np.all(peak_current<=available))
        electrical['checks']['energy']=bool(max(source_power)<=electrical['minimum_driver_dc_power_w'])
        electrical['within_declared_compliance']=all(electrical['checks'].values())
        electrical['scope']='Assigned source-voltage headroom plus sampled reactive driver-current/RF-source-power checks. Prior resistive check retained separately; no physical device stability, bias-current law or between-sample peak qualification.'
        reactive_report=dict(parameters=rf_load,peak_driver_current_a=float(max(peak_current)),
            peak_pad_voltage_v=float(max(abs(network['pad_voltage']))),
            peak_series_cap_voltage_v=None if network['series_cap_voltage'] is None else float(max(abs(network['series_cap_voltage']))),
            final_state=network['final_state'],
            scope='Causal held-envelope RLC response; end/start sampled driver-current checks. No nonlinear current limiting, parasitic uncertainty, device reactive-load stability or between-sample peak proof.')
    emitted_times=rf_times+(1/mix_hz if rf_load is not None else 0.)
    if onset_capture is not None:
        onset=(emitted_times>=1.5e-6)&(emitted_times<5e-6)
        onset_capture.update(times_s=emitted_times[onset].copy(),emitted_v=emitted[onset].copy())
    # Independent analog receiver, then independent fixed-20-MHz observation.
    # This receiver is a diagnostic instrument, not a second chip instance.
    remote = analog_filter(emitted, mix_hz, family='rx_all_pole_control', cutoff_hz=10e6)
    observer_times = 2e-6+correction_delay_s+np.arange(len(wave.samples))/20e6
    observed = (np.interp(observer_times, emitted_times+1/mix_hz, remote.real)+
                1j*np.interp(observer_times, emitted_times+1/mix_hz, remote.imag))
    active = (emitted_times >= 2e-6+correction_delay_s) & (emitted_times < duration-2e-6+correction_delay_s)
    capture = emitted[active]; window = np.hanning(len(capture))
    power = abs(np.fft.fft(capture*window))**2/(len(capture)*np.sum(window**2)*2*load_r)
    offsets = abs(np.fft.fftfreq(len(capture), 1/mix_hz))
    bands = {name:float(np.sum(power[mask])) for name, mask in (
        ('within_10mhz', offsets < 10e6),
        ('offset_10_to_30mhz', (offsets >= 10e6) & (offsets < 30e6)),
        ('offset_30_to_50mhz', (offsets >= 30e6) & (offsets < 50e6)),
        ('offset_above_50mhz', offsets >= 50e6))}
    return dict(**{key:deepcopy(environment[key]) for key in ('diagnostic_input_intervention','diagnostic_input_reason') if key in environment},
        design_provenance=deepcopy(environment.get('design_provenance')),resolved_configuration=deepcopy(config),
        scenario_overrides=deepcopy(environment.get('scenario_overrides',[])),
        scenario_assumptions=deepcopy(environment.get('scenario_assumptions',{})),
        operating_conditions=deepcopy(environment.get('operating_conditions')),
        dac_hz=dac_hz,mixer_hz=mix_hz,cutoff_hz=cutoff_hz,
        oversample=oversample,noise_enabled=noise,fpga_preemphasis=correction,
        noise_sources=dict(converter=noise,aperture=noise),
        input_rms_codes=input_rms_codes,nominal_gain=nominal_gain,pad_series_ohm=pad_series_ohm,
        reactive_load=reactive_report,
        rf_output_parameters=dict(environment['rf_output_parameters'] if driver is not None else TX_PARAMETERS),
        mixer_input_complex_peak_v=float(max(abs(reconstructed))),
        reconstruction_order=reconstruction_order,reconstruction_family=reconstruction_family,converter=converter,dac_enob_hypothesis=enob,dac_aperture_rms_s=aperture,
        dac_full_scale_v=full_scale,
        host_input_clipped_components=int(np.sum(raw != words)),
        electrical=electrical,observation=he_observation(wave, observed),
        scalar_tx_observation=he_scalar_observation(wave,observed,observer_cutoff_hz=10e6),
        loaded_average_active_power_w=float(np.mean(port['load_power_w'][active])),
        observed_rail_interval_v=[float(min(rails)),float(max(rails))],
        local_load_feedback_included='local_load_response' in environment,
        coupled_load_clock=getattr(clock,'load_edge_report',None),
        driver_current_clipped_samples=int(np.sum(clipped)),
        driver_current_clipped_samples_during_source=int(np.sum(clipped & active)),
        emission_band_power_w=bands,
        emission_parseval_residual_w=sum(bands.values())-float(np.sum(abs(capture)**2*window**2)/(2*load_r*np.sum(window**2))),
        fpga_interpolator_taps=64,fpga_interpolator_lookahead_s=32/20e6,
        complete=False,
        scope='Selected native 10-bit DAC and explicitly reported reconstruction order/family/cutoff. Same shared rail/reference/clock realization as RX, external observer with ideal framing and known DATA training. Broad power bands are not a spectral mask. A supplied driver-wake trajectory changes rail/reference/timing and available tail-current limit within the existing 28 mA reservation; otherwise warm constant bias. No signal-dependent RF-cycle current, physical DAC glitches, real FIFO/control lifecycle or external RF filtering. Output impedance/distortion and ENOB remain assigned requirements.')
