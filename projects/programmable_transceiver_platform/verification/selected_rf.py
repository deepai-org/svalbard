"""Selected RF transfer boundaries under the shared baseline environment.

This is a circuit-requirement model, not a transistor or protocol qualification.
No receiver gets the phase realization, converter timestamps or payload truth.
Known DATA training and ideal frame boundaries remain explicit fixture aids.
"""
import math
import numpy as np
from scipy import signal

from behavioral import bandlimited_samples, rf_tx_resistive_port, rf_tx_compliance_budget
from oscillator_noise import PhaseNoise
from protocol_signals import he20
from ble_packet import third_order_frontend
from tx_output_stage import output_envelope
from tx_output_candidate import PARAMETERS as TX_PARAMETERS


def analog_modes(family):
    if family == 'rx_finite_zero':
        b, a = signal.ellip(5, 1, 36.40776933523119, 1, analog=True)
    elif family == 'rx_all_pole_control':
        b, a = signal.butter(5, 1, analog=True)
    elif family == 'tx_third_order':
        b, a = signal.butter(3, 1, analog=True)
    else:
        raise ValueError('Unknown analog transfer family')
    residues, poles, direct = signal.residue(b, a)
    if len(direct):
        raise ValueError('Strictly proper analog response required')
    return residues, poles


def analog_filter(values, sample_hz, *, family, cutoff_hz, interpolation='zoh'):
    """Continuous analog modes with exact constant or linear forcing per step.

    ZOH returns the state at the end of each held interval (legacy convention).
    Linear forcing returns states at the input timestamps, starting from zero.
    Neither method resets at symbol boundaries or uses a fitted filter response.
    """
    if not all(math.isfinite(v) and v > 0 for v in (sample_hz, cutoff_hz)) or interpolation not in ('zoh','linear'):
        raise ValueError('Positive rates and a supported forcing interpolation required')
    values=np.asarray(values)
    if values.ndim!=1 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError('Finite nonempty forcing vector required')
    residues, poles = analog_modes(family)
    exponent = poles * 2 * math.pi * cutoff_hz / sample_hz
    if interpolation=='zoh':
        return sum(r * signal.lfilter([np.expm1(e)/p], [1, -np.exp(e)], values)
                   for r, p, e in zip(residues, poles, exponent))
    result=np.zeros(len(values),complex)
    for residue,pole,e in zip(residues,poles,exponent):
        # expm1(e)-e loses precision for small steps; use its convergent series.
        b=(e/2+e*e/6+e**3/24+e**4/120+e**5/720)/pole if abs(e)<1e-3 else (np.expm1(e)-e)/(pole*e)
        a=np.expm1(e)/pole-b
        out,_=signal.lfilter([b,a],[1,-np.exp(e)],values,zi=[-b*values[0]])
        result+=residue*out
    return result


def analog_hold_at(values, edges, times, *, family, cutoff_hz):
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
    residues,poles=analog_modes(family);rate=2*math.pi*cutoff_hz
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


def rail_at(environment, times):
    return load_value(environment,times,'rail_v') + np.full_like(times, environment['ledger']['local_payload_clock_core_rail_v'], dtype=float) + sum(
        t['clock_rail_voltage_peak_v']*np.cos(2*math.pi*t['frequency_hz']*times+t['voltage_phase_rad'])
        for t in environment['host_spectrum']['tones'])


def reference_at(environment, times):
    return load_value(environment,times,'reference_fraction') + np.ones_like(times, dtype=float) + sum(a*np.cos(2*math.pi*f*times+p)
                   for f, a, p in environment['reference_fraction_tones'])


def load_value(environment,times,field):
    response=environment.get('local_load_response')
    if response is None:return np.zeros_like(times,dtype=float)
    return np.interp(times,response['times_s'],response[field],left=0.,right=0.)


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
    minimum_slope=float(min(evaluate(base,True))-curvature*width-load_slope)
    if minimum_slope<=0:raise ValueError('Cannot certify a monotonic local threshold bracket')
    def residual(t):return evaluate(t)+np.interp(t,times,voltage,left=0.,right=0.)
    low=roots-width;high=roots+width
    if np.any(residual(low)>=0) or np.any(residual(high)<=0):
        raise ValueError('Load perturbation leaves the accepted threshold bracket')
    updated=roots.copy()
    for _ in range(8):
        value=residual(updated)
        high=np.where(value>=0,updated,high);low=np.where(value<0,updated,low)
        candidate=updated-value/evaluate(updated,True)
        updated=np.clip(candidate,low,high)
    voltage_residual=float(max(abs(residual(updated))))
    if voltage_residual>1e-7:raise ValueError('Loaded threshold root did not converge')
    downstream=np.zeros_like(updated)
    for f,v in record['downstream_delay_tones']:
        phase=2*np.pi*f*np.remainder(updated,period)
        downstream+=v.real*np.cos(phase)-v.imag*np.sin(phase)
    output=updated+downstream+np.interp(updated,times,delay,left=0.,right=0.)
    if np.any(np.diff(output)<=0):raise ValueError('Load reverses output edge order')
    return dict(edges_s=output,indices=indices),dict(edge_count=len(output),
        maximum_input_shift_s=float(max(abs(updated-roots))),maximum_root_residual_v=voltage_residual,
        minimum_bracket_slope_v_per_s=minimum_slope,
        scope='Unique ordered local root continuations; extra crossings outside the brackets are not independently excluded.')


class LoadedEdgePhase:
    """Finite perturbed edge interval, with the periodic clock outside it."""
    def __init__(self,periodic,record):
        self.base=periodic;self.carrier=periodic.carrier
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
        self.environment=environment
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

    def phase(self,times):
        return self.source.phase(times)+(0. if self.edge_phase is None else self.edge_phase.phase(times))-(0. if self.coupled_load else 2*math.pi*self.environment['carrier_hz']*load_value(self.environment,times,'delay_s'))

    def crossing_error(self,ideal,carrier):
        if self.edge_phase is not None:
            if abs(carrier-self.edge_phase.carrier)>1e-6:raise ValueError('Edge clock carrier ownership mismatch')
            response=None if self.coupled_load else self.environment.get('local_load_response')
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
        if 'local_load_response' not in self.environment:
            return self.source.crossing_error(ideal,carrier)
        response=self.environment['local_load_response']
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


def wideband_receive(environment, *, oversample=128, wanted_dbm=-85., blocker_dbm=-30.,
                     noise=True, family='rx_finite_zero', gain_settings_db=(42., 48., 54., 60.),
                     sar_parameters=None,load_capture=None,disabled_noise_sources=(),adc_enob=8.,filter_interpolation='zoh',observation_capture=None):
    """Absolute RF -> nonlinear frontend -> loaded LO -> filter -> native ADC.

    Gain sweep is a requirement search, NOT an AGC. All cases carry the same
    received waveform; gain is never selected from held-out decoding results.
    """
    if type(oversample) is not int or oversample < 4:
        raise ValueError('Integer envelope oversampling required')
    if not set(disabled_noise_sources)<={'thermal','converter','aperture'}:
        raise ValueError('Known receiver noise sources required')
    enabled={name:bool(noise and name not in disabled_noise_sources) for name in ('thermal','converter','aperture')}
    if sar_parameters is not None and adc_enob!=8.:
        raise ValueError('Assigned ENOB override is not a causal SAR model parameter')
    wave, drive = he_source(oversample=oversample)
    mix_hz = 20e6*oversample; lo = environment['carrier_hz']; adc_hz = lo/64
    phase = DeliveredClock(environment)
    if max(phase.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+12e6 >= mix_hz/2:
        raise ValueError('Resolve LO sidebands before analog filtering')
    # Include a leading settling interval and trailing FPGA FIR lookahead.
    lead = round(2e-6*mix_hz); tail = round(2e-6*mix_hz)
    drive = np.r_[np.zeros(lead), drive, np.zeros(tail)]
    times = np.arange(len(drive))/mix_hz
    wanted_power = 1e-3*10**((wanted_dbm-2)/10)
    mixed = math.sqrt(100*wanted_power)*drive
    if blocker_dbm is not None:
        mixed += math.sqrt(100*1e-3*10**((blocker_dbm-2)/10))*np.exp(2j*math.pi*12e6*times)
    mixed, nonlinear = third_order_frontend(mixed, 0.)
    if enabled['thermal']:
        rng = np.random.default_rng(901)
        sigma = math.sqrt(50*1.380649e-23*300.15*10**(.6)*mix_hz)
        mixed += sigma*(rng.normal(size=len(times))+1j*rng.normal(size=len(times)))
    rails = rail_at(environment, times)
    mixed *= 10*rails/3.3*np.exp(-1j*phase.phase(times))
    cutoff = 9.53125e6 if family == 'rx_finite_zero' else 9.157407e6
    filtered = analog_filter(mixed, mix_hz, family=family, cutoff_hz=cutoff,interpolation=filter_interpolation)
    ideal = np.arange(1, math.floor(times[-1]*adc_hz)+1)/adc_hz
    actual = ideal+phase.crossing_error(ideal, lo)
    if enabled['aperture']:
        actual += np.random.default_rng(1801).normal(0, 10e-12, len(actual))
    if np.any(np.diff(actual) <= 0):
        raise ValueError('Nonmonotonic converter timestamps')
    # Exact ZOH updates return the analog state at the END of each substep.
    filter_times = times+(1/mix_hz if filter_interpolation=='zoh' else 0.)
    sampled = np.interp(actual, filter_times, filtered.real)+1j*np.interp(actual, filter_times, filtered.imag)
    reference = reference_at(environment, actual)
    headroom = .8*rail_at(environment, actual)/3.3
    observer_times = 2e-6+np.arange(len(wave.samples))/20e6
    rows = []
    for gain_db in gain_settings_db:
        before_clip = sampled*10**(gain_db/20)
        clipped = (abs(before_clip.real) > headroom) | (abs(before_clip.imag) > headroom)
        limited = np.clip(before_clip.real, -headroom, headroom)+1j*np.clip(before_clip.imag, -headroom, headroom)
        if sar_parameters is None:
            words, conversion = native_adc(limited, reference, noise=enabled['converter'],enob=adc_enob)
        else:
            from converter_dynamics import paired_sar
            beginning=actual-sar_parameters.acquisition_s
            start=(np.interp(beginning,filter_times,filtered.real)+1j*np.interp(beginning,filter_times,filtered.imag))*10**(gain_db/20)
            initial_headroom=.8*rail_at(environment,beginning)/3.3
            start=np.clip(start.real,-initial_headroom,initial_headroom)+1j*np.clip(start.imag,-initial_headroom,initial_headroom)
            words,conversion,trace=paired_sar(limited,start,actual,
                lambda t:reference_at(environment,t),lambda t:rail_at(environment,t),
                parameters=sar_parameters,noise=enabled['converter'])
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
        rows.append(dict(pga_gain_db=gain_db,pga_clipped_samples=int(clipped.sum()),
            pga_clipped_samples_during_source=int(clipped[payload].sum()),
            adc=conversion,observation=he_observation(wave, observed)))
    return dict(wanted_antenna_dbm=wanted_dbm,blocker_antenna_dbm=blocker_dbm,
        blocker_offset_hz=12e6,external_loss_db=2.,external_selective_rejection_db=0.,
        chip_input_noise_figure_db=6.,early_voltage_gain_db=20.,input_iip3_dbm=0.,
        frontend_nonlinearity=nonlinear,filter_family=family,cutoff_hz=cutoff,
        native_bits=10,enob_hypothesis=adc_enob if sar_parameters is None else None,
        converter_model='assigned_enob' if sar_parameters is None else 'closed_loop_sar_requirement',
        aperture_rms_s=10e-12,adc_hz=adc_hz,
        mixer_hz=mix_hz,oversample=oversample,filter_interpolation=filter_interpolation,noise_enabled=any(enabled.values()),noise_sources=enabled,
        coupled_load_clock=getattr(phase,'load_edge_report',None),
        observed_rail_interval_v=[float(rails.min()),float(rails.max())],
        reference_interval_v=[float(reference.min()),float(reference.max())],
        resampler_taps=64,fpga_resampler_lookahead_s=32/adc_hz,
        gain_cases=rows,complete=False,
        scope=('Shared loaded source/input/supply spectrum and 236 mA mode budget. Assigned instantaneous early-gain rail sensitivity; fixed NF/IIP3 and ideal linear filter internals. '+
            ('ADC transfer is native 10-bit with assigned excess noise; no SAR/reference-load settling or mismatch. ' if sar_parameters is None else
             'ADC uses causal trial decisions, limited reference recovery and finite acquisition/DAC settling; pole/current/noise hypotheses are unqualified, with no mismatch or comparator-regeneration model. ')+
            'Known DATA training/ideal boundaries, no real preamble, CFO search, AGC or packet/PER qualification. Finite RF record does not qualify emissions or continuous host service.'))


def driver_wake_response(environment, *, released_current_a, wake_start_s,
                         ramp_s=20e-9, grid_s=1e-9, duration_s=12e-6,reference_input=None,guard_s=8e-6):
    """Return from a settled reduced driver load to the budgeted warm load.

    The full 28 mA is ALREADY in the environment's DC ledger. The incremental
    current starts negative and returns to zero; it is never added a second time.
    This is a bounded wake sensitivity, not a prediction of transistor current.
    """
    from robustness_envelope import local_load_state_space
    from converter_dynamics import supply_delay_gain
    delay_gain=supply_delay_gain(environment.get('local_supply_sensitivity_ps_per_mv',.1),environment.get('local_supply_delay_sign',1.))
    if not 0 <= released_current_a <= .028 or ramp_s <= 0 or grid_s <= 0:
        raise ValueError('Wake must stay within the 28 mA driver reservation')
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
        delay=transformed(ports['rail_v_per_a']*delay_gain/(1+1j*frequencies/1e9))
        reference=transformed(ports['rail_v_per_a']*.1/(1+1j*frequencies/10e6))
        input_v=transformed(ports['input_v_per_a'])
        load=.028-released_current_a*(1-np.clip((times-wake_start_s)/ramp_s,0.,1.))
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
            final_current_delta_a=float(load[-1]-.028),peak_clock_shift_s=float(max(abs(delay))),
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
    load=.028+state[:,4]
    if max(abs(state[-1]))>1e-9:
        raise ValueError('Extend the wake record: passive state has not settled')
    result=dict(times_s=times,rail_v=rail,delay_s=filtered(1e9,delay_gain),
        reference_fraction=filtered(10e6,.1),resolved_offset_hz=.5/grid_s,
        driver_current_a=load)
    report=dict(released_current_a=released_current_a,wake_start_s=wake_start_s,
        ramp_s=ramp_s,grid_s=grid_s,driver_current_interval_a=[float(min(load)),float(max(load))],
        initial_rail_relief_v=initial_rail,rail_perturbation_interval_v=[float(min(rail)),float(max(rail))],
        final_current_delta_a=float(state[-1,4]),final_rail_delta_v=float(rail[-1]),
        peak_clock_shift_s=float(max(abs(result['delay_s']))),
        scope='Settled reduced-bias start, continuous passive PDN state and finite current ramp back to the already-budgeted 28 mA. No additional DC load. Assigned delay/reference sensitivities; no signal-dependent RF-cycle current, bias readiness, DAC glitches or substrate coupling.')
    return result,report


def wideband_transmit(environment, *, oversample=128, cutoff_hz=20e6, noise=True,onset_capture=None):
    """FPGA interpolation -> native DAC -> third-order filter -> loaded RF.

    Uses the existing assigned TX output-stage distortion and resistive port.
    The observer has independent timing and no access to the local LO phase.
    """
    wave, _ = he_source(oversample=1)
    lo = environment['carrier_hz']; dac_hz = lo/64; mix_hz = 20e6*oversample
    clock = DeliveredClock(environment)
    if max(clock.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+dac_hz >= mix_hz/2:
        raise ValueError('Resolve TX clock sidebands and first DAC image')
    duration = 4e-6+len(wave.samples)/20e6
    ideal = np.arange(math.ceil(duration*dac_hz)+1)/dac_hz
    edges = ideal+clock.crossing_error(ideal, lo)
    if noise:
        edges += np.random.default_rng(3101).normal(0, 10e-12, len(edges))
    if np.any(np.diff(edges) <= 0):
        raise ValueError('Nonmonotonic DAC timestamps')
    prepared = .12*bandlimited_samples(wave.samples, (ideal-2e-6)*20e6, 32)
    raw = np.stack((np.rint(prepared.real*2048), np.rint(prepared.imag*2048)), axis=-1)
    words = np.clip(raw, -2048, 2047).astype(np.int64)
    analog, converter = native_dac(words, reference_at(environment, edges))
    if noise:
        sigma = math.sqrt((2**(2-16)-(1/512)**2)/12)
        rng = np.random.default_rng(3201)
        analog += sigma*(rng.normal(size=len(edges))+1j*rng.normal(size=len(edges)))*reference_at(environment, edges)
    times = np.arange(math.ceil(duration*mix_hz))/mix_hz
    reconstructed = analog_hold_at(analog, edges, times, family='tx_third_order', cutoff_hz=cutoff_hz)
    rf_times = times
    rails = rail_at(environment, rf_times)
    opened = 4.5*rails/3.3*output_envelope(reconstructed,
        np.exp(1j*clock.phase(rf_times)), **TX_PARAMETERS)
    response=environment.get('local_load_response',{})
    available=np.full(len(times),.028)
    if 'driver_current_a' in response:
        available=np.maximum(0,np.interp(times,response['times_s'],response['driver_current_a'],
            left=response['driver_current_a'][0],right=.028))
    # Current-steering peak differential current cannot exceed its available
    # tail. Do not emit the full waveform while a parked tail is still off.
    limit=available*(40.+50.)
    clipped=abs(opened)>limit
    opened*=np.minimum(1.,limit/np.maximum(abs(opened),1e-30))
    port = rf_tx_resistive_port(opened, source_resistance_ohm=40., load_resistance_ohm=50.)
    emitted = port['envelope_v']
    if onset_capture is not None:
        onset=(times>=1.5e-6)&(times<5e-6)
        onset_capture.update(times_s=times[onset].copy(),emitted_v=emitted[onset].copy())
    electrical = rf_tx_compliance_budget(peak_open_v=float(max(abs(opened))),
        minimum_supply_v=float(min(rails)),total_rail_bias_a=.044,
        source_resistance_ohm=40.,load_resistance_ohm=50.,driver_bias_current_a=.028,
        peak_current_limit_a=.028,headroom_per_rail_v=.3,differential=True)
    # Independent analog receiver, then independent fixed-20-MHz observation.
    # This receiver is a diagnostic instrument, not a second chip instance.
    remote = analog_filter(emitted, mix_hz, family='rx_all_pole_control', cutoff_hz=10e6)
    observer_times = 2e-6+np.arange(len(wave.samples))/20e6
    observed = (np.interp(observer_times, rf_times+1/mix_hz, remote.real)+
                1j*np.interp(observer_times, rf_times+1/mix_hz, remote.imag))
    active = (rf_times >= 2e-6) & (rf_times < duration-2e-6)
    capture = emitted[active]; window = np.hanning(len(capture))
    power = abs(np.fft.fft(capture*window))**2/(len(capture)*np.sum(window**2)*100)
    offsets = abs(np.fft.fftfreq(len(capture), 1/mix_hz))
    bands = {name:float(np.sum(power[mask])) for name, mask in (
        ('within_10mhz', offsets < 10e6),
        ('offset_10_to_30mhz', (offsets >= 10e6) & (offsets < 30e6)),
        ('offset_30_to_50mhz', (offsets >= 30e6) & (offsets < 50e6)),
        ('offset_above_50mhz', offsets >= 50e6))}
    return dict(dac_hz=dac_hz,mixer_hz=mix_hz,cutoff_hz=cutoff_hz,
        reconstruction_order=3,converter=converter,dac_enob_hypothesis=8.,
        host_input_clipped_components=int(np.sum(raw != words)),
        electrical=electrical,observation=he_observation(wave, observed),
        loaded_average_active_power_w=float(np.mean(port['load_power_w'][active])),
        observed_rail_interval_v=[float(min(rails)),float(max(rails))],
        local_load_feedback_included='local_load_response' in environment,
        coupled_load_clock=getattr(clock,'load_edge_report',None),
        driver_current_clipped_samples=int(np.sum(clipped)),
        driver_current_clipped_samples_during_source=int(np.sum(clipped & active)),
        emission_band_power_w=bands,
        emission_parseval_residual_w=sum(bands.values())-float(np.sum(abs(capture)**2*window**2)/(100*np.sum(window**2))),
        fpga_interpolator_taps=64,fpga_interpolator_lookahead_s=32/20e6,
        complete=False,
        scope='Selected native 10-bit DAC and third-order reconstruction at the existing 20 MHz wideband cutoff. Same shared rail/reference/clock realization as RX, external observer with ideal framing and known DATA training. Broad power bands are not a spectral mask. A supplied driver-wake trajectory changes rail/reference/timing and available tail-current limit within the existing 28 mA reservation; otherwise warm constant bias. No signal-dependent RF-cycle current, physical DAC glitches, real FIFO/control lifecycle or external RF filtering. Output impedance/distortion and ENOB remain assigned requirements.')
