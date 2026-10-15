"""Fast RX range screen; not WLAN interoperability or full-chain qualification.

Complete4096-octet coded HE-tone diagnostic, not standard HE PPDU; differential
Barker legacy payload probe without PLCP/acquisition. Known timing in both.
"""
import json
import numpy as np
from scipy.signal import resample_poly
from wideband_packet import source,waveform_source,receive
from selected_rf import analog_filter,he_observation
from he64_packet import source as source64,receive as receive64


from design_definition import load_design


def converter_path(wave,drive,interferer,noise,cutoff,*,integrator_ratio=None):
    rate=80e6;t=np.arange(len(drive))/rate
    filtered=analog_filter(.18*(drive+interferer+noise),rate,family='rx_finite_zero',cutoff_hz=cutoff,interpolation='linear',integrator_ratio=integrator_ratio)
    # Channel1 external LO /64=37.6875MS/s, then FPGA resampling20MS/s.
    times=np.arange(int(np.ceil(len(filtered)*37.6875e6/rate)))/37.6875e6
    native=np.interp(times,t,filtered.real)+1j*np.interp(times,t,filtered.imag)
    clips=int(np.sum((abs(native.real)>1)|(abs(native.imag)>1)))
    native=(np.round(np.clip(native.real,-1,1-1/512)*512)+
            1j*np.round(np.clip(native.imag,-1,1-1/512)*512))/512
    out=resample_poly(native,320,603)[:len(wave.samples)]/.18
    return out,clips


def compare(seed=842):
    rng=np.random.default_rng(seed)
    wave,payload,_=source(seed,payload_bytes=4092)
    qam=source64(payload);_,qam_drive=waveform_source(qam,4)
    _,drive=waveform_source(wave,4)
    rate=80e6;t=np.arange(len(drive))/rate
    noise=.005*(rng.normal(size=len(t))+1j*rng.normal(size=len(t)))/np.sqrt(2)
    blocker=np.sqrt(1000)*np.exp(2j*np.pi*12e6*t)
    bits=np.r_[np.ones(32,dtype=int),rng.integers(0,2,2048)]
    phases=np.cumprod(1-2*bits)
    barker=np.array([1,-1,1,1,-1,1,1,1,-1,-1,-1])
    spread=np.repeat((phases[:,None]*barker).ravel(),4).astype(complex)
    legacy_noise=.02*(rng.normal(size=len(spread))+1j*rng.normal(size=len(spread)))/np.sqrt(2)
    rows=[]
    for cutoff in (9.53125e6,10.5e6,11.5e6):
        row={'cutoff_hz':cutoff}
        for label,interferer in [('clean',0),('cw12mhz',blocker)]:
            out,clips=converter_path(wave,drive,interferer,noise,cutoff)
            decoded,_=receive(out,payload_bytes=4092)
            metrics=he_observation(wave,out)
            row[label]={'diagnostic_crc_ok':decoded['crc_ok'],'held_out_evm':metrics['evm_rms'],'adc_clipped_pairs':clips}
        row['qam64_rate56']={}
        for label in ('clean','cw12mhz'):
            count=len(qam_drive)
            out,clips=converter_path(qam,qam_drive,0 if label=='clean' else blocker[:count],noise[:count],cutoff)
            result=receive64(out,len(payload))
            expected=np.fft.fft(qam.samples.reshape(-1,272)[2:,16:],axis=1)[:,np.array(qam.metadata['data'])%256]/(256/np.sqrt(242))
            evm=float(np.sqrt(np.mean(abs(result['equalized']-expected)**2)/np.mean(abs(expected)**2)))
            row['qam64_rate56'][label]=dict(diagnostic_crc_ok=result['crc_ok'],held_out_evm=evm,adc_clipped_pairs=clips)
        out=analog_filter(spread+legacy_noise,44e6,family='rx_finite_zero',cutoff_hz=cutoff,interpolation='linear')
        symbols=np.sum(out.reshape(-1,44)*np.repeat(barker,4),axis=1)/44
        detected=(np.real(symbols[1:]*symbols[:-1].conj())<0).astype(int)
        row['legacy_probe']={'bit_errors':int(np.sum(detected[31:]!=bits[32:])),
                             'bits':2048,'mean_symbol_power':float(np.mean(abs(symbols[32:])**2)),
                             'known_timing':True,'plcp_implemented':False}
        rows.append(row)
    return dict(result_role='independent_filter_comparison',scope=__doc__,blocker='CW+12MHz,+30dB relative power; no standards blocker claim; ideal linear pre-ADC frontend',
                converter='37.6875MS/s,10bit finite +/-1 range, then FPGA320/603 resampling; no converter noise/dynamic model',
                rows=rows,range_extension_selected=False,
                remaining='Standard legacy/HE packet acquisition, full MCS7 PPDU, complete nonlinear chain and board impairments before range selection')

def tx_radio_compatibility_screen(*,observation_substeps=32,integrator_ratio=None):
    """Linear filter substitution at wide and exploratory narrow settings."""
    from scipy.signal import freqs
    from protocol_signals import gfsk,edr,oqpsk,lora,decisions
    if type(observation_substeps) is not int or observation_substeps<1:
        raise ValueError('Positive integer observation substeps required')
    from selected_rf import _analog_prototype
    rng=np.random.default_rng(740)
    waves=[gfsk(rng.integers(0,2,512),rate=r) for r in (1e6,2e6)]
    waves += [edr(rng.integers(0,n,256),order=n) for n in (4,8)]
    waves += [oqpsk(rng.integers(0,2,1024))]
    waves += [lora(rng.integers(0,128,16),bandwidth=b,oversample=8)
              for b in (203125.,406250.,812500.,1625000.)]
    rows=[]
    for wave in waves:
        nominal=(wave.metadata['bandwidth'] if wave.kind=='lora' else
                 wave.metadata['symbol_rate'] if wave.kind=='gfsk' else
                 2e6 if wave.kind=='oqpsk' else 1e6)
        settings=[('wide', 'tx_third_order',18e6),('wide','rx_all_pole_control',12e6)]
        settings += [(label,family,nominal*scale) for label,scale in
                     (('narrow',1.),('narrow_headroom',2.)) for family in
                     ('tx_third_order','rx_all_pole_control')]
        for setting,family,cutoff in settings:
            numerator,denominator=_analog_prototype(family)
            # Independent nominal response supplies delay, not a DATA fit.
            _,h=freqs(numerator,denominator,np.array([0.,1e-5]))
            if integrator_ratio is not None:
                from selected_rf import analog_modes
                residues,poles=analog_modes(family,integrator_ratio=integrator_ratio)
                if np.any(poles.real>=0):raise ValueError('Unstable radio compatibility filter')
                h=np.sum(residues[None,:]/(1j*np.array([0.,1e-5])[:,None]-poles[None,:]),axis=1)

            delay=-np.angle(h[1]/h[0])/(2*np.pi*cutoff*1e-5)
            padded=np.pad(wave.samples,(0,64))
            # Subdivision preserves the same piecewise-linear stimulus; it
            # refines observation timing without inventing bandwidth or a
            # different pulse-shaping/resampling filter.
            positions=np.arange((len(padded)-1)*observation_substeps+1)/observation_substeps
            fine=(np.interp(positions,np.arange(len(padded)),padded.real)+
                  1j*np.interp(positions,np.arange(len(padded)),padded.imag))
            observation_rate=wave.sample_hz*observation_substeps
            out=analog_filter(fine,observation_rate,family=family,
                cutoff_hz=cutoff,interpolation='linear')
            grid=np.arange(len(out))/observation_rate
            query=np.arange(len(wave.samples))/wave.sample_hz+delay
            observed=np.interp(query,grid,out.real)+1j*np.interp(query,grid,out.imag)
            decoded=decisions(wave,observed);expected=decisions(wave)
            interior=slice(32,-32)
            error=float(np.linalg.norm(observed[interior]-wave.samples[interior])/
                        np.linalg.norm(wave.samples[interior]))
            rows.append(dict(setting=setting,kind=wave.kind,metadata=wave.metadata if wave.kind!='edr' else
                dict(order=wave.metadata['order']),family=family,cutoff_hz=cutoff,
                calibrated_delay_s=delay,relative_waveform_error=error,
                symbol_errors=int(np.sum(decoded!=expected)),symbols=len(expected)))
    return dict(integrator_ratio=integrator_ratio,observation_substeps=observation_substeps,scope='Linear continuous-time filter only, piecewise-linear input, '
        'nominal DC group-delay alignment, no DATA response fit. Narrow cutoff is a '
        'rate/BW-based exploratory setting, not a normative recipe. No DAC images, '
        'startup/turnaround, noise/PA, packets or compliance.',rows=rows)


def tx_image_screen():
    """Exact held-DAC image/main-tone ratio, not a WLAN PSD-mask measurement."""
    from scipy.signal import freqs
    from selected_rf import _analog_prototype
    fs=37.6875e6;rows=[]
    for family,cutoff in [('tx_third_order',18e6),('tx_third_order',10e6),
                          ('rx_finite_zero',9.53125e6),('rx_all_pole_control',12e6)]:
        b,a=_analog_prototype(family)
        for tone in (5e6,9.53125e6):
            image=fs-tone
            _,h=freqs(b,a,np.array([tone,image])/cutoff)
            ratio=abs(np.sinc(image/fs)*h[1]/(np.sinc(tone/fs)*h[0]))
            rows.append(dict(family=family,cutoff_hz=cutoff,tone_hz=tone,
                nearest_image_hz=image,image_relative_to_tone_db=float(20*np.log10(ratio))))
    return dict(scope='Linear continuous-time transfer with exact zero-order-hold sinc; '
        'no quantization/PA/package noise or standard PSD normalization. '
        'RX prototype used only as a sharper reconstruction candidate, not selected hardware.',rows=rows)

def tx_waveform_screen():
    """Held-DAC waveform spectrum and equalized DATA error, not TX compliance."""
    from scipy.signal import welch,freqs
    from selected_rf import _analog_prototype
    from wifi_client_exchange import SharedRFPath,FS,pack,unpack
    rng=np.random.default_rng(603);payload=rng.integers(0,256,4092,dtype=np.uint8).tobytes()
    wave=source64(payload);reference=receive64(wave.samples,len(payload))['equalized']
    native=unpack(pack(resample_poly(.08*wave.samples,603,320)))
    t=np.arange(int(np.ceil(len(native)*80e6/FS)))/80e6
    drive=native[np.minimum((t*FS).astype(int),len(native)-1)]
    rows=[]
    for family,cutoff in [('tx_third_order',18e6),('rx_finite_zero',9.53125e6),('rx_all_pole_control',12e6)]:
        path=SharedRFPath();path.tx_family=family;path.tx_cutoff_hz=cutoff
        out=path.process(drive,'tx',held_values=native)
        sampled=resample_poly(out,1,4)[:len(wave.samples)]
        decoded=receive64(sampled,len(payload),timing_search=True)
        evm=float(np.sqrt(np.mean(abs(decoded['equalized']-reference)**2)/np.mean(abs(reference)**2)))
        # Score steady DATA; transitions and complete PPDU mask remain separate.
        data=out[int(2*272*80e6/20e6):-64]
        f,psd=welch(data,fs=80e6,nperseg=2048,noverlap=1024,return_onesided=False,detrend=False)
        peak=max(psd[abs(f)<=9.53125e6]);relative=10*np.log10(np.maximum(psd,1e-30)/peak)
        def maximum(lo,hi):return float(max(relative[(abs(f)>=lo)&(abs(f)<=hi)]))
        frequencies=np.linspace(0,9.53125e6,2001)
        numerator,denominator=_analog_prototype(family)
        _,transfer=freqs(numerator,denominator,frequencies/cutoff)
        delay=-np.gradient(np.unwrap(np.angle(transfer)),2*np.pi*frequencies)
        rows.append(dict(group_delay_range_ns=[float(min(delay)*1e9),float(max(delay)*1e9)],
            family=family,cutoff_hz=cutoff,crc_ok=decoded['crc_ok'],
            equalized_data_evm=evm,image_band_peak_dbr=maximum(28e6,39e6),
            offset30mhz_peak_dbr=maximum(29.5e6,30.5e6),offset20mhz_peak_dbr=maximum(19.5e6,20.5e6)))
    return dict(scope='4096-octet framed diagnostic, native DAC quantization and held edges, '
        'assigned TX noise/IQ/compression/rail/phase; 80MS/s observation, Hann Welch PSD. '
        'EVM follows training-derived per-tone equalization, NOT uncorrected TX EVM. '
        'No standard packet/window/RBW/absolute-power mask qualification.',rows=rows)

def tx_resampler_kernel(span=10,*,fraction_bits=None):
    """20 MHz to LO/64 channel-1 interpolation prototype; FPGA cost not free."""
    from scipy.signal import firwin
    if type(span) is not int or span<1:raise ValueError('Positive integer resampler span')
    kernel=firwin(2*span*603+1,1/603,window=('kaiser',5))
    if fraction_bits is not None:
        if type(fraction_bits) is not int or fraction_bits<1:
            raise ValueError('Positive integer coefficient fractional precision')
        # FPGA polyphase coefficients include the interpolation gain of 603.
        # scipy applies that gain internally, so undo it only for its API.
        kernel=np.round(kernel*603*2**fraction_bits)/(603*2**fraction_bits)
    return kernel


def tx_fpga_workload(*,resampler_span=40,correction_taps=49,coefficient_bits=16,
                     sample_bits=16,mac_clock_hz=200e6,utilization=.8,
                     resampler_kind='polyphase',sample_hz=None):
    """Unfused real-coefficient I/Q workload; all history belongs to the FPGA."""
    import math
    from fractions import Fraction
    from wifi_client_exchange import FS
    if any(type(x) is not int or x<1 for x in
           (resampler_span,correction_taps,coefficient_bits,sample_bits)):
        raise ValueError('Positive integral filter lengths and storage widths required')
    if not math.isfinite(mac_clock_hz) or mac_clock_hz<=0 or not 0<utilization<=1:
        raise ValueError('Positive MAC rate and bounded utilization required')
    if resampler_kind=='polyphase':
        if sample_hz is not None and sample_hz!=FS:
            raise ValueError('Legacy polyphase kernel requires its characterized sample rate')
        kernel=tx_resampler_kernel(resampler_span)
        phase_lengths=np.array([len(kernel[p::603]) for p in range(603)])
        coefficient_count=len(kernel);phases=603
    elif resampler_kind=='windowed_sinc':
        if sample_hz is None or not math.isfinite(sample_hz) or sample_hz<=0:
            raise ValueError('Explicit native rate required for windowed-sinc workload')
        FS=sample_hz
        phases=(Fraction(str(FS))/Fraction(20000000)).numerator
        phase_lengths=np.array([2*resampler_span])
        coefficient_count=phases*2*resampler_span
    else:raise ValueError('Unknown resampler implementation')
    products=2*(float(np.mean(phase_lengths))+correction_taps)
    rate=FS*products
    return dict(real_products_per_second=rate,sample_hz=FS,resampler_kind=resampler_kind,
        maximum_real_products_per_output_pair=int(2*(max(phase_lengths)+correction_taps)),
        average_resampler_taps_per_phase=float(np.mean(phase_lengths)),
        nominal_resampler_phases=phases,
        coefficient_storage_bytes=math.ceil((coefficient_count+correction_taps)*coefficient_bits/8),
        minimum_history_bytes=math.ceil(2*(int(max(phase_lengths))-1+correction_taps-1)*sample_bits/8),
        resampler_lookahead_s=resampler_span/20e6,
        correction_alignment_delay_s=(correction_taps-1)/(2*FS),
        mac_clock_hz=mac_clock_hz,utilization=utilization,
        required_one_product_per_cycle_lanes=math.ceil(rate/(mac_clock_hz*utilization)),
        additional_chip_storage_bits=0,
        scope='Scheduling lower bound with utilization allowance; independent I/Q products, shared coefficients, no assumed symmetry. Nominal rational-phase table for windowed sinc; asynchronous drift or other rates need a phase-interpolation/table policy. No modem/FEC/RX, memory-port bandwidth, FIFO deadline, finite arithmetic, synthesis or timing closure. Widths are planning assumptions. FIR history and coefficient storage are on the FPGA, excluding packet buffers.')


def tx_preemphasis_coefficients(*,filter_family='rx_all_pole_control',cutoff_hz=12e6,
                               taps=49,coefficient_fraction_bits=12,analog_response=None,stopband_weight=0.,stopband_start_hz=12e6,resampler_span=10,resampler_fraction_bits=None,integrator_ratio=None,sample_hz=None,include_resampler=True):
    """Offline FPGA coefficients fitted to an assumed calibrated TX response."""
    from scipy.signal import freqs,freqz,firwin
    from selected_rf import _analog_prototype
    from wifi_client_exchange import FS
    if type(include_resampler) is not bool:raise ValueError('Explicit resampler inclusion required')
    if sample_hz is not None:
        if not np.isfinite(sample_hz) or sample_hz<=2*9.53125e6:raise ValueError('Native sample rate must cover occupied band')
        if include_resampler and sample_hz!=FS:raise ValueError('Fixed polyphase kernel requires its characterized sample rate')
        FS=sample_hz
    if type(taps) is not int or taps<3 or taps%2!=1:raise ValueError('Odd FIR length')
    if not np.isfinite(cutoff_hz) or cutoff_hz<=0:raise ValueError('Cutoff')
    cutoff=cutoff_hz;delay=(taps-1)//2
    f=np.linspace(0,FS/2,2049);w=2*np.pi*f/FS
    if integrator_ratio is not None:
        if analog_response is not None:raise ValueError('Specify one analog response model')
        from selected_rf import analog_modes
        residues,poles=analog_modes(filter_family,integrator_ratio=integrator_ratio)
        if np.any(poles.real>=0):raise ValueError('Stable reconstruction filter required')
        h=np.sum(residues[None,:]/(1j*f[:,None]/cutoff-poles[None,:]),axis=1)
    elif analog_response is None:
        b,a=_analog_prototype(filter_family);_,h=freqs(b,a,f/cutoff)
    else:
        h=np.asarray(analog_response(f),complex).copy()
        if h.shape!=f.shape or not np.all(np.isfinite(h)):
            raise ValueError('Finite analog response at every fit frequency required')
    h*=np.sinc(f/FS)*np.exp(-.5j*w)
    # Actual resample_poly default FIR, with its compensated linear phase.
    if include_resampler:
        _,digital=freqz(tx_resampler_kernel(resampler_span,fraction_bits=resampler_fraction_bits),worN=2*np.pi*f/(20e6*603))
        h*=abs(digital)
    active=f<=9.53125e6;matrix=np.exp(-1j*w[:,None]*np.arange(taps))
    lhs=matrix[active]*h[active,None];target=np.exp(-1j*w[active]*delay)
    if not np.isfinite(stopband_weight) or stopband_weight<0:raise ValueError('Stopband weight')
    if not np.isfinite(stopband_start_hz) or not 9.53125e6<stopband_start_hz<FS/2:
        raise ValueError('Stopband must follow occupied band and precede Nyquist')
    stop=stopband_weight*matrix[f>=stopband_start_hz]
    coefficients=np.linalg.lstsq(np.r_[lhs.real,lhs.imag,.01*np.eye(taps),stop.real,stop.imag],
        np.r_[target.real,target.imag,np.zeros(taps+2*len(stop))],rcond=None)[0]
    if coefficient_fraction_bits is not None:
        if type(coefficient_fraction_bits) is not int or coefficient_fraction_bits<1:
            raise ValueError('Coefficient fractional precision')
        coefficients=np.round(coefficients*2**coefficient_fraction_bits)/2**coefficient_fraction_bits
    fit_error=lhs@coefficients-target
    return coefficients,delay,float(max(abs(fit_error)))


def tx_tolerance_screen():
    """Linear filter mismatch budget on occupied tones, not packet EVM/PER.

    Independent stage frequency and Q corners replace the misleading assumption
    that all component variation is one common cutoff scale. Extra amplifier
    bandwidth is a deliberately simple lag pole, not an op-amp circuit model.
    """
    import itertools
    from scipy.signal import freqs
    from selected_rf import _analog_prototype
    frequencies=np.r_[np.arange(-122,-1),np.arange(2,123)]*20e6/256
    s=1j*frequencies/12e6
    b,a=_analog_prototype('rx_all_pole_control')
    _,nominal=freqs(b,a,frequencies/12e6)
    def response(errors,lag_hz,retime=False):
        f0,f1,f2,q1,q2=1+np.asarray(errors)
        actual=1/(1+s/f0)
        for frequency,q in ((f1,(np.sqrt(5)-1)/2*q1),(f2,(np.sqrt(5)+1)/2*q2)):
            actual/=1+s/(frequency*q)+(s/frequency)**2
        if lag_hz is not None:actual/=1+1j*frequencies/lag_hz
        ratio=actual/nominal
        if retime:
            # External characterization can update one common waveform delay.
            slope=np.polyfit(frequencies,np.unwrap(np.angle(ratio)),1)[0]
            ratio*=np.exp(-1j*slope*frequencies)
        scalar=np.mean(ratio)
        return float(np.sqrt(np.mean(abs(ratio/scalar-1)**2)))
    rows=[]
    for tolerance in (.001,.005,.01,.02,.05):
        corners=list(itertools.product((-tolerance,tolerance),repeat=5))
        errors=[response(c,None) for c in corners];worst=int(np.argmax(errors))
        rows.append(dict(independent_fraction=tolerance,worst_relative_error=errors[worst],
                         worst_error_db=float(20*np.log10(errors[worst])),
                         worst_stage_errors=list(corners[worst]),
                         worst_error_after_timing_refit=max(response(c,None,True) for c in corners)))
    lags=[dict(lag_pole_hz=hz,relative_error=response(np.zeros(5),hz),
               error_after_timing_refit=response(np.zeros(5),hz,True))
          for hz in (100e6,300e6,1e9)]
    return dict(scope='Stale nominal correction, equal occupied-tone weighting, one complex scalar removed; '
                'timing-refit column also removes fitted common phase slope; no noise/nonlinearity, PER or standard EVM claim. '
                'Stage error order: real pole, biquad1 frequency, biquad2 frequency, Q1, Q2. '
                'Lag pole illustrates missing phase, not an inferred GF180 amplifier bandwidth.',
                corners=rows,unmodeled_lag=lags)


def tx_recalibration_screen():
    """Can sparse external complex-response measurements correct stage mismatch?

    Synthetic measurements and held-out analytic response are distinct grids.
    This is an allocation screen, not proof of measurement equipment accuracy.
    """
    import itertools
    from scipy.signal import freqz,firwin
    from wifi_client_exchange import FS
    measured_f=np.linspace(0,FS/2,129)
    observed_f=(np.arange(122)+.5)*9.53125e6/122
    w=2*np.pi*observed_f/FS
    _,digital=freqz(tx_resampler_kernel(resampler_span,fraction_bits=resampler_fraction_bits),
                   worN=2*np.pi*observed_f/(20e6*603))
    other=np.sinc(observed_f/FS)*np.exp(-.5j*w)*abs(digital)
    def actual(f,errors):
        f0,f1,f2,q1,q2=1+np.asarray(errors);s=1j*f/12e6
        h=1/(1+s/f0)
        for frequency,q in ((f1,(np.sqrt(5)-1)/2*q1),(f2,(np.sqrt(5)+1)/2*q2)):
            h/=1+s/(frequency*q)+(s/frequency)**2
        return h/(1+1j*f/100e6)
    rows=[]
    for tolerance in (.01,.05):
        for measurement_error in (0.,.001,.003):
            worst=0.;largest_gain=0.
            for errors in itertools.product((-tolerance,tolerance),repeat=5):
                h=actual(measured_f,errors)
                # A coherent calibration ripple is not reduced by averaging.
                h*=1+measurement_error*np.exp(2j*np.pi*measured_f/7e6)
                def measured(f):
                    return np.interp(f,measured_f,h.real)+1j*np.interp(f,measured_f,h.imag)
                coefficients,delay,_=tx_preemphasis_coefficients(analog_response=measured)
                _,correction=freqz(coefficients,worN=w)
                error=correction*actual(observed_f,errors)*other*np.exp(1j*w*delay)-1
                worst=max(worst,float(np.sqrt(np.mean(abs(error)**2))))
                _,full=freqz(coefficients,worN=1024)
                largest_gain=max(largest_gain,float(max(abs(full))))
            rows.append(dict(stage_error_fraction=tolerance,coherent_measurement_error=measurement_error,
                worst_heldout_rms_error=worst,maximum_fir_gain=largest_gain,
                within_filter_allocation=worst<=.003))
    return dict(scope='32 corners per row, 129 synthetic complex measurements, 122 held-out frequencies; '
        '49 taps with 12 fractional coefficient bits, real coefficients, 100MHz extra lag. '
        'Includes interpolation and coefficient rounding, excludes measurement timing errors, '
        'post-calibration drift, fixed-point accumulation, nonlinearities and packet emissions.',rows=rows)


def tx_bypass_screen():
    """Ideal stage-bypass compatibility, before switch/loading parasitics."""
    from scipy.signal import freqs
    from selected_rf import _analog_prototype
    f=np.linspace(0,1,1025);s=1j*f
    b,a=_analog_prototype('tx_third_order');_,original=freqs(b,a,f)
    rows=[]
    for q in ((np.sqrt(5)-1)/2,1.,(np.sqrt(5)+1)/2):
        retained=1/((1+s)*(1+s/q+s*s))
        ratio=retained/original
        rows.append(dict(retained_biquad_q=float(q),
            maximum_complex_response_error=float(max(abs(ratio-1))),
            edge_gain_error_db=float(20*np.log10(abs(ratio[-1])))))
    return dict(scope='Ideal unity-gain real pole plus one biquad over DC to cutoff. '
        'Bypass requires Q reconfiguration; switch resistance/capacitance, offset, noise, '
        'power and analog settling are not modeled. Does not select new hardware.',rows=rows)


def tx_integrator_screen():
    """Finite-integrator topology screen, not an inferred transistor GBW."""
    from selected_rf import analog_modes
    from scipy.signal import freqz,firwin
    from wifi_client_exchange import FS
    frequency=(np.arange(244)+.5)*9.53125e6/244
    w=2*np.pi*frequency/FS
    _,digital=freqz(tx_resampler_kernel(resampler_span,fraction_bits=resampler_fraction_bits),
                   worN=2*np.pi*frequency/(20e6*603))
    other=np.sinc(frequency/FS)*np.exp(-.5j*w)*abs(digital)
    rows=[]
    for ratio in (2.,3.,5.,10.,20.,40.):
        residues,poles=analog_modes('rx_all_pole_control',integrator_ratio=ratio)
        stable=bool(max(poles.real)<0)
        row=dict(integrator_pole_to_cutoff_ratio=ratio,
                 effective_pole_hz=12e6*ratio,stable=stable,
                 least_damped_pole_real_hz=float(max(poles.real)*12e6))
        if stable:
            def response(f):
                return np.sum(residues[None,:]/(1j*np.asarray(f)[:,None]/12e6-poles[None,:]),axis=1)
            coefficients,delay,_=tx_preemphasis_coefficients(analog_response=response)
            _,correction=freqz(coefficients,worN=w)
            actual=response(frequency)
            error=correction*actual*other*np.exp(1j*w*delay)-1
            _,full=freqz(coefficients,worN=4096)
            row.update(heldout_rms_error=float(np.sqrt(np.mean(abs(error)**2))),
                       dominant_mode_decay_to_0p1_s=float(np.log(1000)/(-max(poles.real)*2*np.pi*12e6)),
                       maximum_occupied_analog_gain=float(max(abs(actual))),
                       maximum_fir_gain=float(max(abs(full))))
        rows.append(row)
    return dict(scope='Existing surrogate replaces ideal integrators by 1/[s*(1+s/rho)]. '
        'No analog retuning; FPGA49-tap correction fitted to exact synthetic response, '
        '12 fractional coefficient bits, held-out response grid. Effective pole is NOT '
        'op-amp GBW; noise gain, additional amplifier poles, slew, loading and internal '
        'state swing are not established by this screen.',rows=rows)


def tx_internal_state_screen():
    """Chosen voltage-state cascade headroom/load; not transistor feasibility."""
    import itertools
    from selected_rf import rx_filter_state_space,analog_modes
    frequency=np.linspace(0,9.53125e6,257);cutoff=12e6
    input_peak=.25;capacitor=1e-12;rows=[]
    for ratio in (5.,10.,20.):
        for order in itertools.permutations(range(3)):
            model=rx_filter_state_space(family='rx_all_pole_control',order=order,integrator_ratio=ratio)
            matrix=model['A'];b=model['B'];omega=2*np.pi*cutoff
            states=np.linalg.solve(1j*frequency[:,None,None]/cutoff*np.eye(len(b))-matrix,
                                   np.broadcast_to(b,(len(frequency),len(b)))[...,None])[...,0]
            observed=states@model['observers'].T+model['observer_direct']
            output=states@model['C']+model['D']
            residues,poles=analog_modes('rx_all_pole_control',integrator_ratio=ratio)
            reference=np.sum(residues[None,:]/(1j*frequency[:,None]/cutoff-poles[None,:]),axis=1)
            if np.max(abs(output-reference))>1e-8:raise ValueError('State/modal transfer mismatch')
            loads=np.c_[abs(observed[:,:8]),np.ones(len(frequency))]@model['normalized_resistor_load_matrix'].T
            cap_slew=2*np.pi*frequency[:,None]*abs(observed[:,:5])*input_peak
            rows.append(dict(ratio=ratio,section_order=list(order),
                largest_observer_peak_v=float(np.max(abs(observed))*input_peak),
                maximum_integrator_slew_v_per_us=float(np.max(cap_slew)/1e6),
                maximum_single_integrator_cap_current_ua=float(np.max(cap_slew)*capacitor*1e6),
                maximum_single_summer_resistor_current_ua=float(np.max(loads)*omega*capacitor*input_peak*1e6)))
    best=[min((r for r in rows if r['ratio']==ratio),key=lambda r:r['largest_observer_peak_v'])
          for ratio in (5.,10.,20.)]
    return dict(scope='Single-tone differential envelope over occupied band at0.25V input peak and1pF integration capacitors; '
        'explicit LP/BP/drive scaling, conservative resistor-current sums. Not OFDM peak statistics, '
        'summing-amplifier/CMFB power, transistor noise, slew distortion or layout proof.',best_by_ratio=best,rows=rows)


def tx_packet_internal_state_screen(*,substeps=8,amplitude=.08,whitening_seed=None):
    """Exact held-input state updates, sampled peak bounds for candidate OFDM."""
    from scipy.linalg import expm
    from selected_rf import rx_filter_state_space,analog_modes
    from wifi_client_exchange import FS,pack,unpack,validate_tx_samples
    if not np.isfinite(amplitude) or amplitude<=0:raise ValueError('TX amplitude')
    if type(substeps) is not int or substeps<1:raise ValueError('Positive observation substeps')
    cutoff=12e6;ratio=10.;omega=2*np.pi*cutoff
    residues,poles=analog_modes('rx_all_pole_control',integrator_ratio=ratio)
    def response(f):
        return np.sum(residues[None,:]/(1j*np.asarray(f)[:,None]/cutoff-poles[None,:]),axis=1)
    coefficients,_,_=tx_preemphasis_coefficients(analog_response=response,resampler_span=40,
                                               resampler_fraction_bits=14)
    payload=np.random.default_rng(603).integers(0,256,4092,dtype=np.uint8).tobytes()
    native=np.convolve(resample_poly(amplitude*source64(payload,whitening_seed=whitening_seed).samples,603,320,
        window=tx_resampler_kernel(40,fraction_bits=14)),coefficients)
    validate_tx_samples(native)
    native=unpack(pack(native))
    model=rx_filter_state_space(family='rx_all_pole_control',order=(0,1,2),integrator_ratio=ratio)
    a=model['A'];b=model['B'];count=len(b)
    augmented=np.zeros((count+1,count+1));augmented[:count,:count]=a*omega
    augmented[:count,-1]=b*omega
    transition=expm(augmented/(FS*substeps));ad=transition[:count,:count];bd=transition[:count,-1]
    state=np.zeros(count,complex);peak=slew=load=0.
    for u in np.repeat(np.r_[native,np.zeros(80)],substeps):
        observed=model['observers']@state+model['observer_direct']*u
        derivative=(a@state+b*u)*omega
        for component in (np.real,np.imag):
            values=component(observed);input_value=component(u)
            peak=max(peak,float(max(abs(values))))
            slew=max(slew,float(max(abs(component(derivative[:5])))))
            currents=model['normalized_resistor_load_matrix']@np.r_[abs(values[:8]),abs(input_value)]
            load=max(load,float(max(currents))*omega)
        state=ad@state+bd*u
    return dict(whitening_seed=whitening_seed,amplitude=amplitude,observation_substeps=substeps,dac_differential_volts_per_normalized_unit=1.,
        maximum_symmetric_leg_swing_v=peak/2,
        native_component_peak_v=float(max(max(abs(native.real)),max(abs(native.imag)))),
        maximum_internal_component_v=peak,maximum_integrator_slew_v_per_us=slew/1e6,
        capacitor_current_ua_at_2pf=slew*2e-12*1e6,
        summer_resistor_current_ua_at_2pf=load*2e-12*1e6,
        scope='One corrected MCS7 diagnostic packet, quantized DAC, finite-integrator ratio10; '
        '1V differential per normalized DAC unit, linear differential-state voltages. '
        'Symmetric per-leg voltage swing is half; RC/current quantities are equivalent-state '
        'requirements, not a resolved differential amplifier implementation. Sampled maxima, '
        'not continuous peak certification, transistor bias/current, slew limiting or CMFB.')


def tx_amplifier_current_screen(*,design=None):
    """Conditional one-pole gm/noise/bias screen; no GF180 amplifier proof."""
    design=load_design() if design is None else design
    architecture=design.architecture
    ceiling=architecture['rf_interoperability']['external_frontend']['tx_filter_candidate_resource_screen']['per_filter_current_ceiling_ma']
    if isinstance(ceiling,bool) or not isinstance(ceiling,(int,float)) or not np.isfinite(ceiling) or ceiling<=0:
        raise ValueError('Positive finite candidate filter current ceiling required')
    rows=[];kT=1.380649e-23*300.15;gamma=2/3
    noise_gm=4*kT*gamma/(6e-9)**2
    for effective_cap in (.25e-12,.5e-12,1e-12):
        for noise_gain in (2.,4.):
            for efficiency in (5.,10.):
                # Mapping the surrogate pole to closed-loop bandwidth is an
                # explicit hypothesis; compensation and extra poles can break it.
                gm=max(noise_gm,2*np.pi*120e6*noise_gain*effective_cap)
                input_bias=5*gm/efficiency
                reserve=.8e-3
                rows.append(dict(effective_amplifier_cap_f=effective_cap,
                    assumed_noise_gain=noise_gain,assumed_gm_over_id_per_v=efficiency,
                    required_gm_per_amplifier_s=gm,input_bank_a=input_bias,
                    other_circuit_reserve_a=reserve,total_branch_a=input_bias+reserve,
                    candidate_branch_ceiling_ma=ceiling,within_candidate_allocation=bool(input_bias+reserve<=ceiling*1e-3)))
    return dict(design_provenance=design.provenance(),result_role='simplified_component_requirement_screen',
        diagnostic_assumptions=dict(temperature_k=300.15,noise_gamma=2/3,noise_target_v_per_root_hz=6e-9,
            closed_loop_target_hz=120e6,amplifiers_per_branch=5,other_circuit_reserve_a=.8e-3),
        scope='Five single-pole effective amplifiers per I/Q branch,120MHz closed-loop '
        'target,6nV/sqrtHz white input-noise target,gamma=2/3. Assigned effective cap is '
        'not the2pF integration capacitor; topology-dependent noise gain and compensation '
        'must establish their relationship.0.8mA reserves drivers/summers/CMFB/bias but '
        'does not demonstrate their consumption. These are scenario assumptions, not PDK bounds.',rows=rows)


def tx_noise_current_screen():
    """Resistor/assigned amplifier noise versus integration capacitor size."""
    from scipy.linalg import solve_continuous_lyapunov
    from selected_rf import rx_filter_state_space
    model=rx_filter_state_space(family='rx_all_pole_control',order=(0,1,2),integrator_ratio=10.)
    rate=2*np.pi*12e6;kT=1.380649e-23*300.15
    gains=[]
    for n in model['noise_inputs'].T:
        covariance=solve_continuous_lyapunov(model['A'],-np.outer(n,n))
        gains.append(float(rate/2*(model['C']@covariance@model['C'])))
    frequencies=np.linspace(0,10e6,2049)
    matrices=1j*frequencies[:,None,None]/12e6*np.eye(len(model['A']))-model['A']
    transfer=np.linalg.solve(matrices,np.broadcast_to(model['noise_inputs'],
        (len(frequencies),)+model['noise_inputs'].shape))
    response=np.einsum('i,fij->fj',model['C'],transfer)
    from scipy.integrate import trapezoid
    band_gains=trapezoid(abs(response)**2,frequencies,axis=0)
    current_reference=next(r for r in tx_internal_state_screen()['best_by_ratio'] if r['ratio']==10.)
    rows=[]
    for capacitor in (.5e-12,1e-12,2e-12,4e-12):
        resistance=1/(rate*model['normalized_integrator_rates']*capacitor)
        resistor_psd=4*kT*model['resistor_conductance_weights']*resistance
        resistor_variance=float(np.dot(resistor_psd,gains))
        for amplifier_density in (3e-9,6e-9,12e-9):
            noise=np.sqrt(resistor_variance+amplifier_density**2*sum(gains))
            band_noise=np.sqrt(np.dot(resistor_psd,band_gains)+amplifier_density**2*sum(band_gains))
            rows.append(dict(integration_capacitance_f=capacitor,
                amplifier_input_noise_v_sqrt_hz=amplifier_density,
                resistor_only_output_rms_v=float(np.sqrt(resistor_variance)),
                inband_per_branch_rms_v=float(band_noise),inband_complex_rms_v=float(np.sqrt(2)*band_noise),
                inband_fraction_at_80mv_complex=float(np.sqrt(2)*band_noise/.08),
                inband_fraction_at_40mv_complex=float(np.sqrt(2)*band_noise/.04),
                per_branch_output_rms_v=float(noise),complex_output_rms_v=float(np.sqrt(2)*noise),
                fraction_at_80mv_per_branch_signal_rms=float(noise/.08),
                fraction_at_40mv_per_branch_signal_rms=float(noise/.04),
                fraction_at_80mv_complex_signal_rms=float(np.sqrt(2)*noise/.08),
                fraction_at_40mv_complex_signal_rms=float(np.sqrt(2)*noise/.04),
                peak_capacitor_current_ua=current_reference['maximum_single_integrator_cap_current_ua']*capacitor/1e-12,
                peak_summer_resistor_current_ua=current_reference['maximum_single_summer_resistor_current_ua']*capacitor/1e-12,
                resistance_range_ohm=[float(min(resistance)),float(max(resistance))]))
    return dict(scope='One real equivalent branch at300.15K, five independent integrator noise inputs; '
        'ideal resistor/white amplifier noise, finite-bandwidth states/summers noiseless. '
        'Both per-branch and complex-envelope signal references are explicit, not calibrated DAC voltage. '
        'Excludes flicker, mixer/driver/PA noise, reference noise, CMFB and noise correlation. '
        'Amplifier density is assigned, not demonstrated at allocated power.',rows=rows)


def tx_headroom_screen():
    """Separate diagnostic waveform crest from candidate inverse-filter gain."""
    from scipy.signal import freqz
    from wifi_client_exchange import FS
    coefficients,delay,_=tx_preemphasis_coefficients()
    frequencies,response=freqz(coefficients,worN=8192,fs=FS)
    rng=np.random.default_rng(129)
    payloads={'structured':bytes(range(128)),
              'random':rng.integers(0,256,128,dtype=np.uint8).tobytes()}
    rows=[]
    for name,payload in payloads.items():
        for mcs in range(8):
            waveform=source64(payload,mcs=mcs)
            symbols=waveform.samples.reshape(-1,272)
            symbol_peaks=np.max(abs(symbols),axis=1)
            native=resample_poly(.08*waveform.samples,603,320)
            corrected=np.convolve(native,coefficients)
            peak=lambda x:float(max(np.max(abs(x.real)),np.max(abs(x.imag))))
            rows.append(dict(payload=name,mcs=mcs,amplitude=.08,
                peak_symbol_index=int(np.argmax(symbol_peaks)),
                final_symbol_index=len(symbols)-1,
                training_envelope_peak=float(max(symbol_peaks[:2])),
                data_envelope_peak=float(max(symbol_peaks[2:])),
                uncorrected_component_peak=peak(native),corrected_component_peak=peak(corrected),
                uncorrected_overflow=peak(native)>511/512,
                corrected_overflow=peak(corrected)>511/512))
    return dict(scope='Unscrambled diagnostic DATA, not HE packet crest statistics or a power setting. '
                'Includes resampling and candidate FIR before DAC quantization; no clipping is applied.',
                fir_maximum_gain=float(max(abs(response))),
                fir_inband_maximum_gain=float(max(abs(response[frequencies<=9.53125e6]))),
                waveform_delay_s=delay/FS,rows=rows)


def window_diagnostic_ofdm(samples,rolloff_samples):
    """Overlap cyclic suffix with next prefix; diagnostic 256+16 geometry only.

    Useful FFT samples are untouched. Rolloff spends prefix protection and adds
    a final suffix; it is not a general HE preamble/field-boundary formatter.
    """
    if type(rolloff_samples) is not int or not 0<=rolloff_samples<=16:
        raise ValueError('Diagnostic rolloff must fit 16-sample prefix')
    samples=np.asarray(samples,complex)
    if samples.ndim!=1 or len(samples)%272:raise ValueError('Complete diagnostic OFDM rows required')
    if not rolloff_samples:return samples.copy()
    w=rolloff_samples
    rise=.5-.5*np.cos(np.pi*(np.arange(w)+.5)/w)
    output=np.zeros(len(samples)+w,complex)
    for i,row in enumerate(samples.reshape(-1,272)):
        extended=np.r_[row,row[16:16+w]]
        extended[:w]*=rise;extended[-w:]*=1-rise
        output[i*272:i*272+272+w]+=extended
    return output


def tx_preemphasis_screen(*,actual_cutoff_scale=1.,coefficient_fraction_bits=None,
                         filter_family='rx_finite_zero',cutoff_hz=9.53125e6,taps=97,
                         stopband_weight=0.,stopband_start_hz=12e6,payload_bytes=4092,tx_window_samples=0,resampler_span=10,resampler_fraction_bits=None,integrator_ratio=None,mcs=7,amplitude=.08,dac_enob=None,pa_p1db_backoff_db=None,whitening_seed=None,pa_input_p1db_envelope=None,pa_input_loss_db=0.,pa_phase_deg_at_p1db=0.,design=None):
    """FPGA inverse of assumed calibrated TX response; not measured calibration."""
    from scipy.signal import welch
    from wifi_client_exchange import SharedRFPath,FS,pack,unpack,validate_tx_samples
    if not np.isfinite(actual_cutoff_scale) or actual_cutoff_scale<=0:raise ValueError('Cutoff scale')
    if not np.isfinite(amplitude) or amplitude<=0:raise ValueError('TX amplitude')
    design=load_design() if design is None else design
    assigned_enob=design.architecture['model_assumptions']['paired_dac']['parameters']['enob']
    if dac_enob is None:dac_enob=assigned_enob
    if not np.isfinite(dac_enob) or not 0<dac_enob<=10:raise ValueError('DAC ENOB must be within native10-bit width')
    if dac_enob!=assigned_enob:
        design=design.hypothetical(reason='Explicit pre-emphasis DAC-resolution experiment',
            changes={'model_assumptions.paired_dac.parameters.enob':dac_enob})
    architecture=design.architecture
    mask=architecture['rf_interoperability']['tx_spectral_measurement']
    import copy
    allocation=copy.deepcopy(architecture['rf_interoperability']['tx_error_allocation'])
    config=design.configure(engine='rf',direction='tx',reference_hz=2.412e9,sample_divider=64)
    if config.sample_hz!=FS:raise ValueError('Pre-emphasis adapter requires channel-1 /64 sample rate')
    for name in ('dac_i','dac_q'):
        converter=architecture['blocks'][name]['parameters']
        if (converter['native_bits'],converter['transport_bits'],converter['differential_peak_v'])!=(10,12,1.):
            raise ValueError('Pre-emphasis adapter requires 10/12-bit DAC and 1 V normalized full scale')
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=[],result_role='simplified_component_diagnostic',
        model_assumptions=dict(filter_family=filter_family,cutoff_hz=cutoff_hz,
            actual_cutoff_scale=actual_cutoff_scale,integrator_ratio=integrator_ratio,
            reason='Explicit reconstruction-filter candidate; not proof of a legal implemented filter setting',
            converter_noise='Independent white equivalent noise at DAC updates; no DNL, spurs or aperture noise',
            rf_path='SharedRFPath assigned rail/phase/IQ/cubic/additive-noise fixture, not loaded-clock or transistor qualification'))
    cutoff=cutoff_hz
    response=None
    if integrator_ratio is not None:
        from selected_rf import analog_modes
        residues,poles=analog_modes(filter_family,integrator_ratio=integrator_ratio)
        if np.any(poles.real>=0):raise ValueError('Stable reconstruction filter required')
        def response(f):
            return np.sum(residues[None,:]/(1j*np.asarray(f)[:,None]/cutoff_hz-poles[None,:]),axis=1)
    coefficients,delay,fit_error=tx_preemphasis_coefficients(analog_response=response,filter_family=filter_family,
        cutoff_hz=cutoff_hz,taps=taps,coefficient_fraction_bits=coefficient_fraction_bits,
        stopband_weight=stopband_weight,stopband_start_hz=stopband_start_hz,resampler_span=resampler_span,resampler_fraction_bits=resampler_fraction_bits)
    rng=np.random.default_rng(603);payload=rng.integers(0,256,payload_bytes,dtype=np.uint8).tobytes()
    wave=source64(payload,mcs=mcs,whitening_seed=whitening_seed)
    windowed=window_diagnostic_ofdm(wave.samples,tx_window_samples)
    native=np.convolve(resample_poly(amplitude*windowed,603,320,window=tx_resampler_kernel(resampler_span,fraction_bits=resampler_fraction_bits)),coefficients)
    ideal_native=native.copy()
    peak=validate_tx_samples(native)['component_peak'];native=unpack(pack(native))
    native_complex_rms=float(np.sqrt(np.mean(abs(native)**2)))
    # Electrical code-output noise in excess of ideal10-bit quantization.
    # Hold it on actual DAC updates, then apply the same analog reconstruction.
    # This white equivalent-noise hypothesis does not represent DNL or spurs.
    excess_noise_rms=float(np.sqrt(max(0.,((2/2**dac_enob)**2-(1/512)**2)/12)))
    noise_rng=np.random.default_rng(9551)
    native=native+excess_noise_rms*(noise_rng.normal(size=len(native))+1j*noise_rng.normal(size=len(native)))
    t=np.arange(int(np.ceil(len(native)*80e6/FS)))/80e6
    path=SharedRFPath();path.tx_integrator_ratio=integrator_ratio;path.tx_family=filter_family;path.tx_cutoff_hz=cutoff*actual_cutoff_scale
    import copy
    linear_path=copy.deepcopy(path);linear_path.tx_cubic_coefficient=0.
    linear_out=linear_path.process(native[np.minimum((t*FS).astype(int),len(native)-1)],'tx',held_values=native)
    out=path.process(native[np.minimum((t*FS).astype(int),len(native)-1)],'tx',held_values=native)
    ideal_path=SharedRFPath();ideal_path.tx_integrator_ratio=integrator_ratio
    ideal_path.tx_family=filter_family;ideal_path.tx_cutoff_hz=cutoff*actual_cutoff_scale
    ideal_out=ideal_path.process(ideal_native[np.minimum((t*FS).astype(int),len(ideal_native)-1)],
                                 'tx',held_values=ideal_native)
    # Paired paths share all assigned RF/noise realizations; only DAC rounding
    # and excess code-output noise differ. This attributes converter error at
    # the actual operating amplitude, not a nominal sine-backoff assumption.
    occupied_band=abs(np.fft.fftfreq(len(out),1/80e6))<=9.53125e6
    converter_error=np.fft.fft(out-ideal_out)[occupied_band]
    ideal_signal=np.fft.fft(ideal_out)[occupied_band]
    converter_fraction=float(np.linalg.norm(converter_error)/np.linalg.norm(ideal_signal))
    linear_band=np.fft.fft(linear_out)[occupied_band]
    chip_band=np.fft.fft(out)[occupied_band]
    chip_gain=np.vdot(linear_band,chip_band)/np.vdot(linear_band,linear_band)
    chip_residual=float(np.linalg.norm(chip_band-chip_gain*linear_band)/
                        np.linalg.norm(chip_gain*linear_band))
    if not np.isfinite(pa_input_loss_db) or pa_input_loss_db<0:raise ValueError('External TX attenuation')
    if pa_p1db_backoff_db is not None and pa_input_p1db_envelope is not None:
        raise ValueError('Choose relative backoff or fixed PA threshold')
    if pa_input_loss_db and pa_input_p1db_envelope is None:
        raise ValueError('Attenuation comparison requires a fixed PA threshold')
    pa_screen=None
    pa_threshold=None
    if pa_p1db_backoff_db is not None or pa_input_p1db_envelope is not None:
        from rf_power_calibration import pa_compression
        if pa_p1db_backoff_db is not None and not np.isfinite(pa_p1db_backoff_db):raise ValueError('Finite PA backoff required')
        out=out*10**(-pa_input_loss_db/20)
        input_rms=float(np.sqrt(np.mean(abs(out)**2)))
        pa_threshold=(pa_input_p1db_envelope if pa_input_p1db_envelope is not None else input_rms*10**(pa_p1db_backoff_db/20))
        pa_input=out.copy()
        out=pa_compression(out,input_p1db_envelope=pa_threshold,phase_deg_at_p1db=pa_phase_deg_at_p1db)
        pa_error_energy=abs(out-pa_input)**2
        pa_before=np.fft.fft(pa_input)[occupied_band]
        pa_after=np.fft.fft(out)[occupied_band]
        pa_linear_gain=np.vdot(pa_before,pa_after)/np.vdot(pa_before,pa_before)
        pa_residual=float(np.linalg.norm(pa_after-pa_linear_gain*pa_before)/
                          np.linalg.norm(pa_linear_gain*pa_before))

        # Attribute compression to the configured diagnostic geometry without
        # hiding its final padded symbol or removing it from the main score.
        last_symbol_start=(len(wave.samples)-272)/20e6+delay/FS
        last_symbol_mask=t>=last_symbol_start

        pa_screen=dict(phase_deg_at_p1db=pa_phase_deg_at_p1db,input_loss_db=pa_input_loss_db,input_p1db_backoff_db=float(20*np.log10(pa_threshold/input_rms)),
            inband_nonlinear_residual_fraction=pa_residual,
            fitted_inband_gain_magnitude=float(abs(pa_linear_gain)),
            input_rms_envelope=input_rms,input_p1db_envelope=pa_threshold,
            input_crest_db=float(20*np.log10(max(abs(pa_input))/input_rms)),
            samples_above_p1db_fraction=float(np.mean(abs(pa_input)>pa_threshold)),
            final_symbol_compression_error_fraction=float(np.sum(pa_error_energy[last_symbol_mask])/max(np.sum(pa_error_energy),1e-30)),

            qualification=False,scope='Assigned memoryless AM/AM and optional power-dependent AM/PM; fixed threshold '
            'for burst and tail. No absolute power, memory, noise or recovery qualification.')
    # Observer interpolates finely to the declared calibrated delay. It does
    # not estimate/undo frequency-selective TX response from received DATA.
    # An EVM observer must reject out-of-channel images before 20MS/s
    # sampling; otherwise those images alias into the scored constellation.
    observer=out
    padded=np.pad(observer,(2048,2048));bins=np.fft.fftfreq(len(padded),1/80e6)
    selected=np.fft.ifft(np.fft.fft(padded)*(abs(bins)<=10e6))[2048:-2048]
    high=resample_poly(selected,8,1);grid=np.arange(len(high))/640e6
    query=np.arange(len(wave.samples))/20e6+delay/FS
    observed=np.interp(query,grid,high.real)+1j*np.interp(query,grid,high.imag)
    x=np.fft.fft(wave.samples.reshape(-1,272)[:,16:],axis=1)
    y=np.fft.fft(observed.reshape(-1,272)[:,16:],axis=1)
    occupied=np.r_[wave.metadata['data'],wave.metadata['pilots']]%256
    data=np.array(wave.metadata['data'])%256
    gain=np.vdot(x[:2,occupied],y[:2,occupied])/np.vdot(x[:2,occupied],x[:2,occupied])
    evm=float(np.sqrt(np.mean(abs(y[2:,data]/gain-x[2:,data])**2)/np.mean(abs(x[2:,data])**2)))
    steady=out[int(2*272*4+delay*80e6/FS):-64]
    segment=min(2048,len(steady))
    frequencies,psd=welch(steady,fs=80e6,nperseg=segment,
        noverlap=segment//2,return_onesided=False,detrend=False)
    relative=10*np.log10(np.maximum(psd,1e-30)/max(psd[abs(frequencies)<=cutoff]))
    image_peak=float(max(relative[(abs(frequencies)>=28e6)&(abs(frequencies)<=39e6)]))
    # Capture the physical filter tail after the DAC's final zero transition.
    # FFT the complete finite burst: no edge slicing or artificial taper that
    # would suppress the very switching spectrum being measured.
    tail=path.process(np.zeros(160,complex),'idle')
    if pa_threshold is not None:
        tail=pa_compression(tail*10**(-pa_input_loss_db/20),input_p1db_envelope=pa_threshold,phase_deg_at_p1db=pa_phase_deg_at_p1db)
    burst=np.r_[out,tail]
    frequency=np.fft.fftfreq(len(burst),1/80e6)
    energy=abs(np.fft.fft(burst))**2
    inband=float(sum(energy[abs(frequency)<=10e6]))
    bands={f'{lo:g}_{hi:g}_MHz':float(10*np.log10(max(
        sum(energy[(abs(frequency)>lo*1e6)&(abs(frequency)<=hi*1e6)])/inband,1e-30)))
        for lo,hi in ((10,20),(20,28),(28,39))}
    from selected_rf import relative_burst_mask_screen
    mask_screen=relative_burst_mask_screen(burst,80e6,mask)
    import copy
    from rf_quality_budget import evaluate_budget
    converter_allowance=allocation['uncorrelated_rms_fraction']['converter']
    if pa_screen is not None:
        nonlinear_allowance=allocation['bounded_residual_fraction']['nonlinearity_including_external_pa']
        # Express both residuals against the same cascaded scalar reference.
        # The chip LS residual is orthogonal to that reference, so its output
        # norm is sqrt(1+r_chip^2) times the reference norm. Add norms; no
        # cancellation between chip and PA distortion is credited.
        nonlinear_bound=chip_residual+pa_residual*np.sqrt(1+chip_residual**2)
        pa_screen.update(chip_nonlinear_residual_fraction=chip_residual,
            cascaded_nonlinearity_bound=float(nonlinear_bound),
            cascade_within_nonlinearity_allowance=bool(nonlinear_bound<=nonlinear_allowance),
            total_nonlinearity_allowance=nonlinear_allowance,
            remaining_chip_nonlinearity_allowance=nonlinear_allowance-pa_residual,
            pa_alone_within_nonlinearity_allowance=pa_residual<=nonlinear_allowance,
            allocation_scope='PA residual after one fitted complex scalar over active-burst '
            '+/-9.53125MHz. Remaining deterministic norm budget also must cover chip '
            'distortion without cancellation; negative remainder rejects this operating point.')

    allocation['uncorrelated_rms_fraction']['converter']=converter_fraction
    combined=evaluate_budget(allocation)
    combined.update(converter_allowance=converter_allowance,
        converter_meets_allocation=converter_fraction<=converter_allowance,
        scope='Replace only converter term with paired-path in-band RMS attribution; '
        'all other errors retain normative allocations. Assumes independent white '
        'equivalent converter noise, not physical DAC DNL/spurs or standard TX EVM.')
    tail_fraction=float(sum(abs(tail)**2)/sum(abs(burst)**2))
    return dict(context,whitening_seed=whitening_seed,pa_screen=pa_screen,combined_allocation_screen=combined,converter_inband_error_fraction=converter_fraction,
        dac_enob=dac_enob,dac_excess_noise_per_branch_rms=excess_noise_rms,
        native_complex_rms=native_complex_rms,native_sine_referenced_backoff_db=float(-20*np.log10(native_complex_rms)),
        integrator_ratio=integrator_ratio,resampler_fraction_bits=resampler_fraction_bits,resampler_span=resampler_span,resampler_lookahead_s=resampler_span/20e6,
        relative_mask_screen=mask_screen,full_burst_band_energy_dbc=bands,tail_energy_fraction=tail_fraction,
        tx_window_samples=tx_window_samples,remaining_prefix_s=(16-tx_window_samples)/20e6,
        mcs=mcs,amplitude=amplitude,payload_bytes=payload_bytes,scope='Assumed calibrated linear response, FPGA FIR with optional rounded coefficients, '
        'one packet/seed and assigned TX impairments. Ideal 20MHz band-selected, scalar-only observer EVM; '
        'not standard PPDU/mask or physical qualification. Calibration error, '
        'accumulator arithmetic, latency integration and resource cost remain open.',
        filter_family=filter_family,cutoff_hz=cutoff,
        actual_cutoff_scale=actual_cutoff_scale,coefficient_fraction_bits=coefficient_fraction_bits,
        stopband_weight=stopband_weight,stopband_start_hz=stopband_start_hz,
        taps=taps,waveform_delay_s=delay/FS,native_component_peak=peak,image_band_peak_dbr=image_peak,
        maximum_linear_fit_error=fit_error,scalar_only_evm=evm,
        scalar_only_evm_db=float(20*np.log10(evm)),
        crc_ok=receive64(observed,len(payload),mcs=mcs,whitening_seed=whitening_seed)['crc_ok'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tx-fpga-workload',action='store_true')
    parser.add_argument('--tx-packet-internal-state',action='store_true')
    parser.add_argument('--tx-amplifier-current',action='store_true')
    parser.add_argument('--tx-noise-current',action='store_true')
    parser.add_argument('--tx-internal-state',action='store_true')
    parser.add_argument('--tx-integrator',action='store_true')
    parser.add_argument('--tx-bypass',action='store_true')
    parser.add_argument('--tx-recalibration',action='store_true')
    parser.add_argument('--tx-tolerance',action='store_true')
    parser.add_argument('--tx-headroom',action='store_true')
    parser.add_argument('--tx-radio-compatibility',action='store_true')
    parser.add_argument('--tx-images',action='store_true')
    parser.add_argument('--tx-waveform',action='store_true')
    parser.add_argument('--integrator-ratio',type=float)
    parser.add_argument('--resampler-fraction-bits',type=int)
    parser.add_argument('--resampler-span',type=int,default=10)
    parser.add_argument('--tx-window-samples',type=int,default=0)
    parser.add_argument('--payload-bytes',type=int,default=4092)
    parser.add_argument('--tx-preeq',action='store_true')
    parser.add_argument('--mcs',type=int,choices=range(8),default=7)
    parser.add_argument('--amplitude',type=float,default=.08)
    parser.add_argument('--dac-enob',type=float,help='Explicit DAC ENOB experiment; defaults to the shared design')
    parser.add_argument('--pa-p1db-backoff-db',type=float)
    parser.add_argument('--pa-input-p1db-envelope',type=float)
    parser.add_argument('--pa-input-loss-db',type=float,default=0.)
    parser.add_argument('--pa-phase-deg-at-p1db',type=float,default=0.)
    parser.add_argument('--whitening-seed',type=int,help='Diagnostic known-mask padding control, not standard HE scrambling')
    parser.add_argument('--actual-cutoff-scale',type=float,default=1.)
    parser.add_argument('--coefficient-fraction-bits',type=int)
    parser.add_argument('--filter-family',choices=['rx_finite_zero','rx_all_pole_control'],default='rx_finite_zero')
    parser.add_argument('--cutoff-hz',type=float,default=9.53125e6)
    parser.add_argument('--taps',type=int,default=97)
    parser.add_argument('--stopband-weight',type=float,default=0.)
    parser.add_argument('--stopband-start-hz',type=float,default=12e6)
    args=parser.parse_args()
    print(json.dumps(tx_amplifier_current_screen() if args.tx_amplifier_current else tx_packet_internal_state_screen(amplitude=args.amplitude,whitening_seed=args.whitening_seed) if args.tx_packet_internal_state else tx_fpga_workload(resampler_span=args.resampler_span,correction_taps=args.taps) if args.tx_fpga_workload else tx_radio_compatibility_screen(integrator_ratio=args.integrator_ratio) if args.tx_radio_compatibility else tx_noise_current_screen() if args.tx_noise_current else tx_internal_state_screen() if args.tx_internal_state else tx_integrator_screen() if args.tx_integrator else tx_bypass_screen() if args.tx_bypass else tx_recalibration_screen() if args.tx_recalibration else tx_tolerance_screen() if args.tx_tolerance else tx_headroom_screen() if args.tx_headroom else tx_preemphasis_screen(actual_cutoff_scale=args.actual_cutoff_scale,coefficient_fraction_bits=args.coefficient_fraction_bits,filter_family=args.filter_family,cutoff_hz=args.cutoff_hz,taps=args.taps,stopband_weight=args.stopband_weight,stopband_start_hz=args.stopband_start_hz,payload_bytes=args.payload_bytes,tx_window_samples=args.tx_window_samples,resampler_span=args.resampler_span,resampler_fraction_bits=args.resampler_fraction_bits,integrator_ratio=args.integrator_ratio,mcs=args.mcs,amplitude=args.amplitude,dac_enob=args.dac_enob,pa_p1db_backoff_db=args.pa_p1db_backoff_db,whitening_seed=args.whitening_seed,pa_input_p1db_envelope=args.pa_input_p1db_envelope,pa_input_loss_db=args.pa_input_loss_db,pa_phase_deg_at_p1db=args.pa_phase_deg_at_p1db) if args.tx_preeq else tx_waveform_screen() if args.tx_waveform else tx_image_screen() if args.tx_images else compare(),indent=2))
