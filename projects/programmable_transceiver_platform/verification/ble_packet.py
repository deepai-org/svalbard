"""External BLE source/observer around existing generic RF blocks.

Core 6.1 Vol 6 B 2.1/3 and Vol 6 C 4.2.1:
https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/low-energy-controller/sample-data.html
No packet parsing, whitening or CRC is proposed on the transceiver.
"""
import json
import math
import numpy as np
from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/"system_model/architecture_fast"))
sys.path.insert(0,str(P/"system_model/connected"))
from behavioral import (multipole_envelope, adc_reference_conversion, bandlimited_samples,
    timed_dac_playback,rf_tx_resistive_port,rf_tx_compliance_budget)
from tx_output_stage import output_envelope
from tx_output_candidate import PARAMETERS as TX_PARAMETERS
from oscillator_noise import PhaseNoise
from resource_configuration import validate_rf_settings, rf_transition_budget
from check_contract import periodic_stream_bound
from protocol_signals import gfsk, ble_advertising_bits, ble_whiten, ble_crc_bits


def observe(samples,*,fs=10e6,channel=38):
    """Search timing/CFO from preamble+AA only; no start, payload or CFO oracle."""
    sps=round(fs/1e6)
    if sps<4 or sps*1e6!=fs:raise ValueError('Integer LE 1M oversampling required')
    z=np.asarray(samples,complex)
    frequency=np.angle(z[1:]*z[:-1].conj())*fs/(2*math.pi)
    prefix=ble_advertising_bits(bytes([2,0]),channel)[:40]
    known=2*prefix[:38]-1
    best=None;first_candidate=None
    # Average the central half of each bit, suppressing Gaussian transitions.
    def symbols(start,count):
        indices=start+np.arange(count)[:,None]*sps+np.arange(sps//4,3*sps//4)[None,:]
        return frequency[indices].mean(axis=1)
    for start in range(max(0,len(frequency)-40*sps)):
        # Once the first AA-qualified hypothesis arrives, compare timing phases
        # for one bit period only. Never use later payload to choose acquisition.
        if first_candidate is not None and start>first_candidate+sps:break
        values=symbols(start,38)
        slope=float(np.dot(known-known.mean(),values-values.mean())/np.sum((known-known.mean())**2))
        if slope<=0:continue
        offset=float(values.mean()-slope*known.mean())
        residual=float(np.mean((values-offset-slope*known)**2)/slope**2)
        if residual>.35 or not np.array_equal((symbols(start,40)>offset).astype(int)[8:40],prefix[8:40]):continue
        if first_candidate is None:first_candidate=start
        if best is None or residual<best[0]:best=(residual,start,offset,slope)
    if best is None:return dict(acquired=False,crc_ok=False)
    decision_sample=first_candidate+41*sps+1
    if len(z)<decision_sample:return dict(acquired=False,crc_ok=False)
    residual,start,offset,slope=best
    count=(len(frequency)-start)//sps
    bits=(symbols(start,count)>offset).astype(int)
    result=dict(acquired=True,crc_ok=False,start_sample=start,cfo_estimate_hz=offset,fit_residual=residual,
        acquisition_decision_sample=decision_sample,acquisition_decision_s=decision_sample/fs)
    if len(bits)<56:return result
    data=ble_whiten(bits[40:],channel)
    octets=[sum(int(b)<<j for j,b in enumerate(data[i:i+8])) for i in range(0,len(data)-7,8)]
    size=2+(octets[1]&63)
    if len(data)<8*size+24:return result
    result['crc_decision_sample']=start+(40+8*size+24)*sps+1
    result['crc_decision_s']=result['crc_decision_sample']/fs
    result['crc_ok']=bool(np.array_equal(ble_crc_bits(data[:8*size]),data[8*size:8*size+24]))
    if result['crc_ok']:result['pdu_hex']=bytes(octets[:size]).hex()
    return result


def bounded_gain_conversion(filtered,adc_noise,*,fs=10e6,command_latency_s=2e-6,
                            initial_gain_db=40.,maximum_gain_db=60.,reference_scale=None,pga_peak_v=.8):
    """ADC-observed generic gain control; no wanted-power or packet oracle.

    One pending command, 1 us observation windows, <=6 dB steps, assigned
    0.2 us gain settling. These are requirements for a host/control path,
    not proof the present command interface implements this service.
    """
    if not all(math.isfinite(v) for v in (fs,command_latency_s,initial_gain_db,maximum_gain_db)) or fs<1e6 or command_latency_s<0 or not 0<=initial_gain_db<=maximum_gain_db:
        raise ValueError('Bounded gain and nonnegative command latency required')
    z=np.asarray(filtered,complex);noise=np.asarray(adc_noise,complex)
    if z.shape!=noise.shape or z.ndim!=1:raise ValueError('One noise value per sample required')
    reference=np.ones(len(z)) if reference_scale is None else np.asarray(reference_scale,float)
    if reference.shape!=z.shape or not np.all(np.isfinite(reference)) or np.any(reference<=0) or not math.isfinite(pga_peak_v) or pga_peak_v<=0:
        raise ValueError('Positive reference per sample and physical PGA headroom required')
    window=round(fs*1e-6);delay=math.ceil(command_latency_s*fs)
    target_db=initial_gain_db;gain=10**(target_db/20);alpha=-math.expm1(-1/(fs*.2e-6))
    pending=None;result=[];trace=[];clipped=0;adc_clipped=0;updates=0;energy=0.
    step=2/4096
    for i,value in enumerate(z):
        if pending is not None and i>=pending[0]:
            target_db=pending[1];pending=None;updates+=1
        gain+=alpha*(10**(target_db/20)-gain)
        raw=value*gain
        clipped+=int(abs(raw.real)>pga_peak_v or abs(raw.imag)>pga_peak_v)
        output=(complex(np.clip(raw.real,-pga_peak_v,pga_peak_v),np.clip(raw.imag,-pga_peak_v,pga_peak_v))+noise[i])/reference[i]
        adc_clipped+=int(abs(output.real)>1 or abs(output.imag)>1)
        code=complex(round(np.clip(output.real,-1,1-step)/step)*step,
                     round(np.clip(output.imag,-1,1-step)/step)*step)
        result.append(code);trace.append(20*math.log10(gain));energy+=abs(code)**2
        if (i+1)%window==0:
            measured=math.sqrt(energy/window);energy=0.
            if pending is None:
                correction=float(np.clip(20*math.log10(.12/max(measured,step)),-6.,6.))
                next_db=float(np.clip(target_db+correction,0.,maximum_gain_db))
                pending=(i+1+delay,next_db)
    return np.asarray(result),dict(gain_db=trace,pga_clipped_samples=clipped,adc_clipped_samples=adc_clipped,
        applied_updates=updates,command_latency_s=command_latency_s,
        initial_gain_db=initial_gain_db,maximum_gain_db=maximum_gain_db,
        pga_peak_v=pga_peak_v,reference_scale_min=float(reference.min()),reference_scale_max=float(reference.max()))


def transport_service(contract, *, sample_hz, word_hz):
    t=contract['transport']
    return periodic_stream_bound(arrival_item_hz=sample_hz*(1+t['source_fast_ppm']/1e6),
        item_bits=24,word_hz=word_hz*(1-t['host_slow_ppm']/1e6),
        frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
        staging_frames=t['scheduling']['staging_frames'],cdc_words=2)


def response_budget(observation,settings,environment,contract,*,advertiser_address,
                    observer_hz=10e6,fpga_work_s=2e-6,analog_settle_s=2e-6):
    """FPGA policy and generic service timeline, not a transmitted RF waveform.

    Source start/payload never enter this decision. Air deadline is estimated
    from decoded timing. A separate scoreboard may compare it to source truth.
    """
    if not all(math.isfinite(v) and v>=0 for v in (fpga_work_s,analog_settle_s)):
        raise ValueError('Finite nonnegative processing and settling budgets required')
    decoded=bytes.fromhex(observation.get('pdu_hex',''))
    accepted=(observation.get('crc_ok',False) and len(decoded)==14 and
              decoded[0]&15==3 and decoded[0]&0x80 and decoded[1]==12 and decoded[8:14]==advertiser_address)
    if not accepted:return dict(request_accepted=False,reply_armed=False,reason='No valid addressed scan request')
    fs=settings['sample_hz'];word=environment['host_spectrum']['d2h_word_hz']
    h2d=environment['host_spectrum']['h2d_word_hz']
    down=transport_service(contract,sample_hz=fs,word_hz=word)
    up=transport_service(contract,sample_hz=fs,word_hz=h2d)
    if not (down['rate_stable'] and up['rate_stable']):
        return dict(request_accepted=True,reply_armed=False,reason='Insufficient sustained sample service',
            transport=dict(d2h=down,h2d=up))
    packet_bits=40+8*len(decoded)+24
    estimated_end=observation['start_sample']/observer_hz+packet_bits/1e6
    target=estimated_end+150e-6
    events=[]
    now=observation['crc_decision_s']
    def stage(name,duration,owner):
        nonlocal now
        events.append(dict(state=name,start_s=now,end_s=now+duration,owner=owner))
        now+=duration
    stage('deliver_last_required_samples',down['delay_bound_s'],'chip/host transport')
    stage('resampler_lookahead',32/fs,'FPGA')
    stage('CRC_address_policy_and_response_generation',fpga_work_s,'FPGA')
    stage('wait_for_command_frame',64/h2d,'host transport')
    transition=rf_transition_budget(before=settings,after=settings,operation='turnaround',
        epoch=7,host_word_hz=h2d,command_words=8,cdc_cycles=2,control_hz=40e6,
        boundary_wait_s=64/word,analog_settle_s=analog_settle_s,source_lock_s=0.,
        host_training_words=0,fpga_recovery_s=0.,deadline_s=150e-6,d2h_lo_divider=32)
    for event in transition['events']:
        stage(event['state'],event['end_s']-event['start_s'],event['owner'])
    # A small continuous-stream prefill, never a whole packet on the chip.
    prefill_bits=32*24
    stage('response_sample_prefill',up['service_latency_s']+prefill_bits/up['guaranteed_service_bps'],'FPGA/host transport')
    reserve=contract['transport']['scheduling']['ingress_bits_per_source']
    service_fits=(down['rate_stable'] and up['rate_stable'] and
                  max(down['backlog_bound_bits'],prefill_bits+up['backlog_bound_bits'])<=reserve and
                  prefill_bits>=up['backlog_bound_bits'])
    ready=now
    armed=service_fits and ready<=target
    if armed:stage('wait_for_timestamped_launch',target-now,'generic timed action')
    return dict(request_accepted=True,reply_armed=armed,estimated_request_end_s=estimated_end,
        target_air_start_s=target,ready_s=ready,preparation_margin_s=target-ready,
        fpga_work_s=fpga_work_s,events=events,turnaround=transition,
        transport=dict(d2h=down,h2d=up,prefill_bits=prefill_bits,
            tx_prefill_plus_service_backlog_bits=prefill_bits+up['backlog_bound_bits'],comparison_storage_bits=reserve,
            sustained_service_and_storage_fit=service_fits),
        air_launch_timing_verified=False,reply_waveform_verified=False,
        scope='Scheduled readiness under assigned service bounds. RX timestamp calibration, DAC/filter launch delay, actual controls and TX settling/emissions remain unverified.')


def third_order_frontend(envelope, input_iip3_dbm, impedance_ohm=50.):
    """Input-referred memoryless cubic, valid only for modest compression.

    For equal RF envelope tones, IM3 power extrapolates to 3*Pin-2*IIP3.
    This equivalent front-end hypothesis precedes channel filtering; it is not
    a device model, hard saturation model or a validated gain/noise tradeoff.
    """
    z=np.asarray(envelope,complex)
    if not np.all(np.isfinite(z)) or not math.isfinite(input_iip3_dbm) or not math.isfinite(impedance_ohm) or impedance_ohm<=0:
        raise ValueError('Finite envelope, IIP3 and positive impedance required')
    intercept_w=1e-3*10**(input_iip3_dbm/10)
    fraction=abs(z)**2/(2*impedance_ohm*intercept_w)
    peak=float(np.max(fraction)) if len(z) else 0.
    return z*(1-fraction),dict(input_iip3_dbm=input_iip3_dbm,
        maximum_cubic_gain_reduction_fraction=peak,
        within_assigned_small_compression_range=peak<=.1,
        scope='Ten-percent peak cubic gain reduction is an assigned model-validity screen, not a compression specification.')


def joined_scan_request(environment,contract,*,seed=81,wanted_dbm=-80.,
                        blocker_dbm=-40.,blocker_attenuation_db=2.,mixer_substeps=256,include_noise=True,
                        fpga_work_s=2e-6,noise_figure_db=10.,adc_enob=8.,
                        initial_gain_db=40.,thermal_noise_enabled=True,adc_noise_enabled=True,
                        rx_cutoff_hz=.7e6,blocker_offsets_hz=(2e6,),input_iip3_dbm=None):
    """Real packet RX through one declared rail/clock/reference environment.

    Wide internal envelope sampling resolves LO sidebands before analog filtering;
    only filtered values reach the actual divided-LO ADC clock. All gain control
    and packet decisions use received codes. RF source truth is scoreboard-only.
    """
    if environment['payload_engine']!='rf' or not math.isclose(environment['carrier_hz'],2.426e9):
        raise ValueError('This external channel-38 fixture requires an RF environment at 2426 MHz')
    if type(mixer_substeps) is not int or mixer_substeps not in (256,512):
        raise ValueError('Resolved mixer refinement required')
    if not math.isfinite(noise_figure_db) or noise_figure_db<0 or not math.isfinite(adc_enob) or not 1<=adc_enob<=12:
        raise ValueError('Finite nonnegative NF and 1..12 ENOB required')
    noise_factor=10**(noise_figure_db/10)
    lo=environment['carrier_hz'];fs=lo/256;observer_hz=10e6;source_hz=40e6
    settings=validate_rf_settings(sample_hz=fs,tx_cutoff_hz=1.5e6,rx_cutoff_hz=rx_cutoff_hz,
        rx_filter_order=5,sample_clock_source='external_lo',lo_hz=lo,lo_divider=256)
    rng=np.random.default_rng(seed)
    advertiser=bytes.fromhex('a6a5a4a3a2c1')
    # Both addresses are static random (two most significant bits set).
    scanner=rng.bytes(5)+bytes([0xc1])
    pdu=bytes([0xc3,12])+scanner+advertiser
    bits=ble_advertising_bits(pdu,38);wave=gfsk(bits,fs=source_hz)
    source=wave.samples[wave.metadata['delay']:wave.metadata['delay']+len(bits)*40]
    start_s=float(rng.uniform(2e-6,12e-6));cfo=float(rng.choice([-80000,0,80000]))
    duration=start_s+len(bits)/1e6+12e-6
    mix_hz=fs*mixer_substeps;times=np.arange(math.ceil(duration*mix_hz))/mix_hz
    positions=(times-start_s)*source_hz
    # External continuous-phase stimulus: phase interpolation at an independent
    # 40 MHz source grid, not a waveform generated on the local ADC clock.
    phase=np.interp(positions,np.arange(len(source)),np.unwrap(np.angle(source)))
    gate=(positions>=0)&(positions<len(source))
    wanted_w=1e-3*10**((wanted_dbm-2.)/10)
    mixed=math.sqrt(2*50*wanted_w)*gate*np.exp(1j*(phase+2*math.pi*cfo*times))
    if not blocker_offsets_hz or any(not math.isfinite(f) or f<=0 for f in blocker_offsets_hz):
        raise ValueError('Positive finite external blocker offsets required')
    if blocker_dbm is not None:
        blocker_w=1e-3*10**((blocker_dbm-blocker_attenuation_db)/10)
        for offset in blocker_offsets_hz:
            mixed+=math.sqrt(2*50*blocker_w)*np.exp(2j*math.pi*(offset+cfo)*times)
    nonlinearity=None
    if input_iip3_dbm is not None:
        mixed,nonlinearity=third_order_frontend(mixed,input_iip3_dbm)
    clock=PhaseNoise(tuple(environment['delivered_phase_tones']))
    if clock.maximum_offset_hz+max(blocker_offsets_hz)+abs(cfo)>=mix_hz/2:
        raise ValueError('Unresolved LO sidebands must not alias through the receive filter')
    mixed*=np.exp(-1j*clock.phase(times))
    # Fixed input-referred thermal PSD, before the analog filter. Complex
    # envelope power is E|z|²/(2R); noise factor and T=300.15 K are hypotheses.
    noise_sigma=math.sqrt(50*1.380649e-23*300.15*noise_factor*mix_hz)
    if include_noise and thermal_noise_enabled:
        noise_rng=np.random.default_rng(seed+900)
        mixed+=noise_sigma*(noise_rng.normal(size=len(times))+1j*noise_rng.normal(size=len(times)))
    rail=environment['ledger']['local_payload_clock_core_rail_v']
    filtered=multipole_envelope(mixed*10*rail/3.3,mix_hz,settings['rx_cutoff_hz'],settings['rx_filter_order'])
    filter_times=times+1/mix_hz
    ideal=np.arange(1,math.floor(duration*fs)+1)/fs
    actual=ideal+clock.crossing_error(ideal,lo)
    if include_noise:actual+=np.random.default_rng(seed+1800).normal(0,.3e-12,len(actual))
    if np.any(np.diff(actual)<=0):raise ValueError('Nonmonotonic ADC timestamps')
    sampled=np.interp(actual,filter_times,filtered.real)+1j*np.interp(actual,filter_times,filtered.imag)
    reference=1+sum(a*np.cos(2*math.pi*f*actual+p) for f,a,p in environment['reference_fraction_tones'])
    step=2/4096
    sigma=math.sqrt(max(0.,2**(2-2*adc_enob)-step**2)/12)
    noise_rng=np.random.default_rng(seed+1900)
    adc_noise=sigma*(noise_rng.normal(size=len(actual))+1j*noise_rng.normal(size=len(actual))) if include_noise and adc_noise_enabled else np.zeros(len(actual),complex)
    d2h=environment['host_spectrum']['d2h_word_hz'];h2d=environment['host_spectrum']['h2d_word_hz']
    service=transport_service(contract,sample_hz=fs,word_hz=d2h)
    agc_delay=service['delay_bound_s']+.5e-6+64/h2d+8/h2d+2/40e6+1/fs
    codes,agc=bounded_gain_conversion(sampled,adc_noise,fs=fs,command_latency_s=agc_delay,
        reference_scale=reference,pga_peak_v=.8*rail/3.3,initial_gain_db=initial_gain_db)
    trace=agc.pop('gain_db')
    agc.update(minimum_gain_db=min(trace),maximum_observed_gain_db=max(trace),final_gain_db=trace[-1])
    # Nominal code timestamps only: actual jitter/reference are NOT handed to
    # FPGA reconstruction. Lookahead is explicitly charged in response_budget.
    observer_times=np.arange(math.floor(ideal[-1]*observer_hz))/observer_hz
    observed=bandlimited_samples(codes,observer_times*fs-1,32,cutoff=min(1.,observer_hz/fs))
    observation=observe(observed,fs=observer_hz,channel=38)
    reply=response_budget(observation,settings,environment,contract,
        advertiser_address=advertiser,fpga_work_s=fpga_work_s)
    if reply['request_accepted']:
        reply['scoreboard_uncalibrated_end_error_s']=reply['estimated_request_end_s']-(start_s+len(bits)/1e6)
    peak=sum(t['clock_rail_voltage_peak_v'] for t in environment['host_spectrum']['tones'])
    return dict(seed=seed,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,
        blocker_attenuation_db=blocker_attenuation_db,wanted_insertion_loss_db=2.,
        blocker_offsets_hz=list(blocker_offsets_hz),frontend_nonlinearity=nonlinearity,
        settings=settings,source_start_s=start_s,source_packet_end_s=start_s+len(bits)/1e6,
        source_cfo_hz=cfo,mixer_hz=mix_hz,mixer_substeps=mixer_substeps,
        sample_count=len(codes),adc_crossing_rms_s=float(np.sqrt(np.mean((actual-ideal)**2))),
        thermal_noise_density_v2_per_hz=2*50*1.380649e-23*300.15*noise_factor,
        noise_figure_db=noise_figure_db,adc_enob=adc_enob,
        thermal_noise_enabled=include_noise and thermal_noise_enabled,
        adc_noise_enabled=include_noise and adc_noise_enabled,
        include_noise=include_noise,gain_control=agc,observation=observation,
        correct_request=observation.get('pdu_hex')==pdu.hex(),response=reply,
        conservative_local_rail_interval_v=[rail-peak,rail+peak],
        linear_fixture_voltage_range_guaranteed=rail-peak>=2.5 and rail+peak<=3.6,
        complete=False,
        scope='Conditional packet RX and response-readiness timeline. Assigned NF, early gain, gain range, rail scaling, reference rejection and service. No physical early-stage compression, AGC ABI, real TX waveform or protocol-compliance claim.')


def rf_emission_bands(envelope,sample_hz,load_ohm=50.):
    """Windowed loaded power by offset band; no protocol/regulatory mask.

    Complex voltage is a peak RF envelope: power is E|v|²/(2R).
    Hann energy normalization preserves this scale for the weighted record.
    """
    z=np.asarray(envelope,complex)
    if (z.ndim!=1 or len(z)<4 or not np.all(np.isfinite(z)) or
            not all(math.isfinite(x) and x>0 for x in (sample_hz,load_ohm))):
        raise ValueError('Finite envelope and positive sample rate/load required')
    window=np.hanning(len(z));energy=float(np.sum(window**2))
    bins=abs(np.fft.fft(z*window))**2/(len(z)*energy*2*load_ohm)
    offset=abs(np.fft.fftfreq(len(z),1/sample_hz))
    masks={'within_1mhz':offset<1e6,'offset_1_to_3mhz':(offset>=1e6)&(offset<3e6),
        'offset_3_to_40mhz':(offset>=3e6)&(offset<40e6),'offset_above_40mhz':offset>=40e6}
    bands={name:float(np.sum(bins[mask])) for name,mask in masks.items()}
    direct=float(np.sum(abs(z)**2*window**2)/(energy*2*load_ohm))
    return dict(band_power_w=bands,window_weighted_total_w=direct,
        parseval_residual_w=sum(bands.values())-direct,resolved_offset_limit_hz=sample_hz/2,
        scope='Hann-weighted full burst at declared resistive load, before any external RF filter. Broad offset integrals are not measurement-bandwidth emission limits; unmodeled RF harmonics and physical switching transients remain excluded.')


def transmitted_scan_response(request,environment,contract,*,rx_timestamp_correction_s=0.,
                              tx_launch_advance_s=0.,host_gap_s=0.,mixer_substeps=256):
    """Prepared FPGA reply -> finite FIFO -> actual DAC edges -> loaded RF -> peer.

    Source request end is used only in the returned scoreboard. Launch policy
    uses the decoded timestamp and explicit calibration values. The remote
    receiver has independent sample timing and sees no transmitted bits.
    """
    reply=request['response']
    if not reply['reply_armed']:
        return dict(transmitted=False,reason='Reply not armed',complete=False)
    if (not all(math.isfinite(x) and x>=0 for x in
                (rx_timestamp_correction_s,tx_launch_advance_s,host_gap_s)) or
            mixer_substeps not in (256,512)):
        raise ValueError('Finite nonnegative timing bounds and resolved mixer required')
    fs=request['settings']['sample_hz'];lo=environment['carrier_hz'];source_hz=40e6
    # FPGA packet generation: advertiser address comes from the accepted request,
    # with a short valid complete-local-name AD structure. No chip packet fields.
    decoded=bytes.fromhex(request['observation']['pdu_hex'])
    payload=decoded[8:14]+b'\x03\x09SV'
    pdu=bytes([0x44,len(payload)])+payload
    bits=ble_advertising_bits(pdu,38);wave=gfsk(bits,fs=source_hz)
    source=.25*wave.samples[wave.metadata['delay']:wave.metadata['delay']+len(bits)*40]
    count=math.ceil((len(bits)/1e6+4e-6)*fs)
    prepared=bandlimited_samples(source,np.arange(count)*source_hz/fs,32,cutoff=fs/source_hz)
    codes,dac_clips=adc_reference_conversion(prepared,np.ones(count),12)
    desired=reply['target_air_start_s']-rx_timestamp_correction_s-tx_launch_advance_s
    # Assigned generic 40 MHz timestamp counter, then the first eligible DAC edge.
    trigger=math.ceil(desired*40e6)/40e6
    if reply['ready_s']>trigger:
        return dict(transmitted=False,reason='Prepared too late for corrected launch',complete=False)
    clock=PhaseNoise(tuple(environment['delivered_phase_tones']))
    begin=math.floor(reply['ready_s']*fs)-2
    end=math.ceil(trigger*fs)+count+8
    ideal=np.arange(begin,end)/fs
    edges=ideal+clock.crossing_error(ideal,lo)
    prefill=reply['transport']['prefill_bits']//24
    # FPGA paces on the known consumption rate. Transport is a declared bounded
    # delay, not an instantaneous read from the full prepared FPGA waveform.
    arrivals=np.r_[np.full(prefill,reply['ready_s']),
        trigger+np.arange(1,count-prefill+1)/fs+reply['transport']['h2d']['delay_bound_s']+host_gap_s]
    played,queue=timed_dac_playback(codes,arrivals,edges,launch_s=trigger,
        depth_samples=contract['transport']['scheduling']['ingress_bits_per_source']//24,
        minimum_prefill_samples=prefill)
    if queue['first_consumption_s'] is None:
        return dict(transmitted=False,reason=queue['fault'],playback=queue,complete=False)
    launch=queue['first_consumption_s'];stop=queue['fault_time_s']
    if stop is None:stop=queue['last_consumption_s']+1/fs
    reference=1+sum(a*np.cos(2*math.pi*f*edges+p) for f,a,p in environment['reference_fraction_tones'])
    rng=np.random.default_rng(request['seed']+3000)
    sigma=math.sqrt(max(0.,2**(2-16)-(2/4096)**2)/12)
    analog_codes=(played+sigma*(rng.normal(size=len(edges))+1j*rng.normal(size=len(edges))))*reference
    mix_hz=fs*mixer_substeps;window_start=trigger-4e-6
    times=window_start+np.arange(math.ceil((count/fs+8e-6)*mix_hz))/mix_hz
    indices=np.searchsorted(edges,times,side='right')-1
    held=analog_codes[np.clip(indices,0,len(edges)-1)]
    # Existing causal reconstruction filter; phase rotation remains on the same
    # absolute source realization used during the received request (no reset).
    reconstructed=multipole_envelope(held,mix_hz,request['settings']['tx_cutoff_hz'],1)
    rail=environment['ledger']['local_payload_clock_core_rail_v']
    gain=4.5*rail/3.3
    rf_times=times+1/mix_hz
    opened=gain*output_envelope(reconstructed,np.exp(1j*clock.phase(rf_times)),**TX_PARAMETERS)
    # Assigned 50 ns output-enable rise, hard fail-mute. This is an explicit
    # transient hypothesis, not evidence about physical switching splatter.
    gate=np.where((rf_times>=launch)&(rf_times<stop),-np.expm1(-np.maximum(0,rf_times-launch)/50e-9),0.)
    opened*=gate
    port=rf_tx_resistive_port(opened,source_resistance_ohm=40.,load_resistance_ohm=50.)
    emitted=port['envelope_v']
    rail_peak=sum(t['clock_rail_voltage_peak_v'] for t in environment['host_spectrum']['tones'])
    electrical=rf_tx_compliance_budget(peak_open_v=float(np.max(abs(opened))),
        minimum_supply_v=rail-rail_peak,total_rail_bias_a=.037,
        source_resistance_ohm=40.,load_resistance_ohm=50.,driver_bias_current_a=.028,
        peak_current_limit_a=.028,headroom_per_rail_v=.3,differential=True)
    # Independent remote downconversion/filter/sampling: no shared-LO subtraction,
    # no local DAC timestamps and no payload-fitted phase or frequency correction.
    remote=multipole_envelope(emitted*np.exp(-2j*math.pi*request['source_cfo_hz']*rf_times),mix_hz,.7e6,5)
    peer_hz=10e6;peer_times=window_start+np.arange(math.floor((times[-1]-window_start)*peer_hz))/peer_hz+37e-9
    samples=np.interp(peer_times,rf_times+1/mix_hz,remote.real)+1j*np.interp(peer_times,rf_times+1/mix_hz,remote.imag)
    peer=observe(samples,fs=peer_hz,channel=38)
    # Diagnostic RF-envelope threshold only, not the standard's first-bit timing
    # definition. Peer acquisition includes its own path delay too.
    threshold=.5*.25*gain*50/90
    above=np.flatnonzero(abs(emitted)>=threshold)
    half_start=float(rf_times[above[0]]) if len(above) else None
    if peer['acquired']:peer['absolute_start_estimate_s']=float(peer_times[0]+peer['start_sample']/peer_hz)
    active=(rf_times>=launch)&(rf_times<min(stop,launch+len(bits)/1e6))
    return dict(transmitted=True,complete=False,playback=queue,dac_clipped_samples=dac_clips,
        rx_timestamp_correction_s=rx_timestamp_correction_s,tx_launch_advance_s=tx_launch_advance_s,
        host_gap_s=host_gap_s,desired_launch_s=desired,control_trigger_s=trigger,
        first_dac_consumption_s=launch,rf_half_amplitude_start_s=half_start,
        scoreboard_rf_half_amplitude_gap_s=None if half_start is None else half_start-request['source_packet_end_s'],
        peer=peer,peer_correct_response=peer.get('pdu_hex')==pdu.hex(),
        fpga_waveform_storage='Static scan-response samples can be prepared in FPGA memory before the request; no full-packet chip buffer',
        fpga_source_interpolator_taps=64,
        loaded_average_active_power_w=float(np.mean(port['load_power_w'][active])),
        loaded_peak_envelope_v=float(np.max(abs(emitted))),electrical=electrical,
        emission_bands=rf_emission_bands(emitted,mix_hz),
        phase_time_origin_reset=False,reference_scale_min=float(reference.min()),reference_scale_max=float(reference.max()),
        linear_fixture_voltage_range_guaranteed=request['linear_fixture_voltage_range_guaranteed'],
        air_launch_timing_qualified=False,
        scope='Loaded reply waveform and independent strong-signal peer under assigned driver, gate and host-service models. Envelope threshold is a diagnostic marker, not certified first-bit timing. No TX-load PDN feedback, physical switch transients, peer sensitivity, emissions mask or real bridge/command qualification.')


def campaign():
    rows=[];fs=10e6;amplitude=.12
    for seed in (17,81,203):
        rng=np.random.default_rng(seed)
        pdu=bytes([0x42,14])+bytes.fromhex('a6a5a4a3a2c1')+rng.bytes(8)
        bits=ble_advertising_bits(pdu);wave=gfsk(bits,fs=fs)
        packet=wave.samples[wave.metadata['delay']:wave.metadata['delay']+len(bits)*10]
        # Unknown arrival with silence before/after; no synthetic prefix.
        start=int(rng.integers(20,120));offset=float(rng.choice([-80000,0,80000]))
        source=np.r_[np.zeros(start),packet,np.zeros(100)]
        times=np.arange(len(source))/fs
        for cutoff in (.7e6,1.5e6):
            for wanted in (-65.,-80.,-90.):
                wanted_w=1e-3*10**((wanted-2)/10)
                noise_rms=amplitude*math.sqrt(1.380649e-23*300.15*10*fs/wanted_w)
                # Noise PSD follows fixed NF, not the wanted amplitude. Gain is
                # still ideally set per wanted level: actual AGC remains open.
                for blocker_dbm in (None,-40.):
                    mixed=amplitude*source*np.exp(2j*math.pi*offset*times)
                    if blocker_dbm is not None:
                        level=amplitude*10**((blocker_dbm-20-(wanted-2))/20)
                        mixed+=level*np.exp(2j*math.pi*(2e6+offset)*times)
                    noise=np.random.default_rng(seed+900).normal(size=(len(source),2))
                    mixed+=noise_rms*(noise[:,0]+1j*noise[:,1])/math.sqrt(2)
                    filtered=multipole_envelope(mixed,fs,cutoff,5)
                    enob_noise=2**(1-8)/math.sqrt(12)
                    adc_noise=np.random.default_rng(seed+1900).normal(size=(len(source),2))
                    adc_noise=enob_noise*(adc_noise[:,0]+1j*adc_noise[:,1])
                    # Map the old normalized linear filter output back to volts
                    # after a fixed 20 dB early conversion gain. All later gain
                    # is controlled from observed ADC codes, never wanted power.
                    physical=filtered*math.sqrt(2*50*wanted_w)*10/amplitude
                    for gain_mode,latency in (('ideal_per_case',None),('bounded_agc',2e-6),('bounded_agc',8e-6)):
                        agc=None
                        if latency is None:
                            adc,clipped=adc_reference_conversion(filtered+adc_noise,np.ones(len(filtered)),12)
                        else:
                            adc,agc=bounded_gain_conversion(physical,adc_noise,fs=fs,command_latency_s=latency)
                            clipped=agc['adc_clipped_samples']
                            gain_trace=agc.pop('gain_db')
                            agc.update(gain_at_preamble_end_db=gain_trace[start+80-1],
                                gain_at_access_address_end_db=gain_trace[start+400-1],
                                final_gain_db=gain_trace[-1],minimum_gain_db=min(gain_trace),peak_gain_db=max(gain_trace))
                        observation=observe(adc,fs=fs)
                        rows.append(dict(seed=seed,wanted_dbm=wanted,blocker_dbm=blocker_dbm,
                            cutoff_hz=cutoff,cfo_hz=offset,adc_clipped_samples=clipped,
                            gain_mode=gain_mode,gain_control=agc,
                            observation=observation,correct_packet=observation.get('pdu_hex')==pdu.hex()))
    return dict(cases=rows,complete=False,
        scope='Real LE 1M framing, causal prefix acquisition, existing generic filter/ADC. Ideal-gain control retained beside ADC-driven bounded AGC with assigned command latency, gain settling and PGA clipping. Early-stage compression, NF versus gain, phase transients and host service implementation unqualified; no full power/timing join, PER confidence or compliance.')


if __name__=='__main__':
    result=campaign()
    for cutoff in (.7e6,1.5e6):
        for wanted in (-65.,-80.,-90.):
            for blocker in (None,-40.):
                for mode,latency in (('ideal_per_case',None),('bounded_agc',2e-6),('bounded_agc',8e-6)):
                    rows=[r for r in result['cases'] if (r['cutoff_hz'],r['wanted_dbm'],r['blocker_dbm'],r['gain_mode'],(r['gain_control'] or {}).get('command_latency_s'))==(cutoff,wanted,blocker,mode,latency)]
                    print(cutoff,wanted,blocker,mode,latency,sum(r['correct_packet'] for r in rows),'/',len(rows))
