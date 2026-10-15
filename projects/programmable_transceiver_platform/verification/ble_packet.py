"""External BLE source/observer around existing generic RF blocks.

Core 6.1 Vol 6 B 2.1/3 and Vol 6 C 4.2.1:
https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/low-energy-controller/sample-data.html
No packet parsing, whitening or CRC is proposed on the transceiver.
"""
import json
from copy import deepcopy
import math
import numpy as np
from pathlib import Path
import sys
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/"system_model/architecture_fast"))
sys.path.insert(0,str(P/"system_model/connected"))
from design_definition import validate_contract_provenance
from behavioral import (multipole_envelope, adc_reference_conversion, bandlimited_samples,
    timed_dac_playback,rf_tx_resistive_port,rf_tx_compliance_budget)
from tx_output_stage import output_envelope
from tx_output_candidate import PARAMETERS as TX_PARAMETERS
from oscillator_noise import PhaseNoise
from resource_configuration import validate_rf_settings, rf_transition_budget
from check_contract import periodic_stream_bound
from protocol_signals import gfsk, ble_advertising_bits, ble_whiten, ble_crc_bits


def prbs15_bits(count):
    """Maximal x^15+x^14+1 sequence; initial state all ones, MSB first."""
    if type(count) is not int or count<0:raise ValueError('Nonnegative bit count required')
    state=0x7fff;bits=np.empty(count,dtype=np.uint8)
    for i in range(count):
        bits[i]=(state>>14)&1
        state=((state<<1)|(((state>>14)^(state>>13))&1))&0x7fff
    return bits


def reference_interferer_phase(times):
    """Nominal LE 1M GFSK PRBS15 stimulus, not a qualified RF test generator."""
    times=np.asarray(times,float)
    if times.ndim!=1 or not len(times) or not np.all(np.isfinite(times)) or np.any(times<0):
        raise ValueError('Finite nonnegative observation times required')
    fs=40e6;sps=40;prefix=8
    bits=prbs15_bits(int(math.ceil(max(times)*1e6))+2*prefix+4)
    wave=gfsk(bits,rate=1e6,h=.5,fs=fs)
    # Discard source startup shaping; interpolate phase, preserving unit envelope.
    position=times*fs+wave.metadata['delay']+prefix*sps
    return np.interp(position,np.arange(len(wave.samples)),np.unwrap(np.angle(wave.samples)))


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
                            initial_gain_db=40.,maximum_gain_db=60.,reference_scale=None,pga_peak_v=.8,
                            converter_bits=12,gain_response_tau_s=.2e-6,gain_codes_db=None):
    """ADC-observed generic gain control; no wanted-power or packet oracle.

    Default 12-bit precision and continuous 40–60 dB gain are standalone
    functional assumptions, not the selected native ADC/PGA allocation.

    One pending command, 1 us observation windows, <=6 dB steps, assigned
    gain response pole. These are assumptions for a host/control path,
    not proof the present command interface implements this service.
    """
    codes=None if gain_codes_db is None else tuple(gain_codes_db)
    if codes is not None and (not codes or any(not math.isfinite(v) for v in codes) or
            tuple(sorted(set(codes)))!=codes or initial_gain_db not in codes or maximum_gain_db!=max(codes)):
        raise ValueError('Ordered supported PGA codes and matching gain bounds required')
    minimum_gain_db=0. if codes is None else min(codes)
    if not all(math.isfinite(v) for v in (fs,command_latency_s,initial_gain_db,maximum_gain_db)) or fs<1e6 or command_latency_s<0 or not minimum_gain_db<=initial_gain_db<=maximum_gain_db:
        raise ValueError('Bounded gain and nonnegative command latency required')
    if isinstance(gain_response_tau_s,bool) or not math.isfinite(gain_response_tau_s) or gain_response_tau_s<=0:
        raise ValueError('Positive finite PGA response time required')
    z=np.asarray(filtered,complex);noise=np.asarray(adc_noise,complex)
    if z.shape!=noise.shape or z.ndim!=1:raise ValueError('One noise value per sample required')
    reference=np.ones(len(z)) if reference_scale is None else np.asarray(reference_scale,float)
    headroom=np.broadcast_to(np.asarray(pga_peak_v,float),z.shape)
    if (reference.shape!=z.shape or not np.all(np.isfinite(reference)) or np.any(reference<=0) or
            not np.all(np.isfinite(headroom)) or np.any(headroom<=0) or converter_bits not in (10,12)):
        raise ValueError('Positive reference per sample and physical PGA headroom required')
    window=round(fs*1e-6);delay=math.ceil(command_latency_s*fs)
    target_db=initial_gain_db;gain=10**(target_db/20);alpha=-math.expm1(-1/(fs*gain_response_tau_s))
    pending=None;result=[];trace=[];commands=[];clipped=0;adc_clipped=0;updates=0;energy=0.
    step=2/(1<<converter_bits)
    for i,value in enumerate(z):
        if pending is not None and i>=pending[0]:
            target_db=pending[1];pending=None;updates+=1
        gain+=alpha*(10**(target_db/20)-gain)
        raw=value*gain
        clipped+=int(abs(raw.real)>headroom[i] or abs(raw.imag)>headroom[i])
        output=(complex(np.clip(raw.real,-headroom[i],headroom[i]),np.clip(raw.imag,-headroom[i],headroom[i]))+noise[i])/reference[i]
        adc_clipped+=int(abs(output.real)>1 or abs(output.imag)>1)
        code=complex(round(np.clip(output.real,-1,1-step)/step)*step,
                     round(np.clip(output.imag,-1,1-step)/step)*step)
        result.append(code);trace.append(20*math.log10(gain));energy+=abs(code)**2
        if (i+1)%window==0:
            measured=math.sqrt(energy/window);energy=0.
            if pending is None:
                correction=float(np.clip(20*math.log10(.12/max(measured,step)),-6.,6.))
                next_db=float(np.clip(target_db+correction,minimum_gain_db,maximum_gain_db))
                if codes is not None:next_db=min(codes,key=lambda value:abs(value-next_db))
                commands.append(next_db)
                pending=(i+1+delay,next_db)
    return np.asarray(result),dict(gain_db=trace,pga_clipped_samples=clipped,adc_clipped_samples=adc_clipped,
        applied_updates=updates,command_latency_s=command_latency_s,
        gain_response_tau_s=gain_response_tau_s,gain_codes_db=codes,commanded_gain_db=commands,
        initial_gain_db=initial_gain_db,maximum_gain_db=maximum_gain_db,
        pga_peak_v=float(headroom.min()),pga_peak_range_v=[float(headroom.min()),float(headroom.max())],
        converter_bits=converter_bits,transport_bits=12,
        native_transport_low_two_bits_zero=(bool(np.all(np.rint(np.array([np.real(result),np.imag(result)])*2048).astype(np.int64)%4==0)) if converter_bits==10 else None),
        reference_scale_min=float(reference.min()),reference_scale_max=float(reference.max()))


def transport_service(contract, *, sample_hz, word_hz):
    t=contract['transport']
    return periodic_stream_bound(arrival_item_hz=sample_hz*(1+t['source_fast_ppm']/1e6),
        item_bits=24,word_hz=word_hz*(1-t['host_slow_ppm']/1e6),
        frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
        staging_frames=t['scheduling']['staging_frames'],cdc_words=2)


def packet_control_clock(environment):
    """Use the bound counter rate; 40 MHz belongs only to primitive fixtures."""
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if bound and 'control_hz' not in environment:
        raise ValueError('Design-bound packet requires control clock')
    frequency=environment.get('control_hz',40e6)
    if isinstance(frequency,bool) or not isinstance(frequency,(int,float)) or not math.isfinite(frequency) or frequency<=0:
        raise ValueError('Positive finite packet control clock required')
    return frequency


def response_budget(observation,settings,environment,contract,*,advertiser_address,
                    observer_hz=10e6,fpga_work_s=2e-6,analog_settle_s=2e-6,conversion_latency_s=0.,host_samples_ready_s=None):
    """FPGA policy and generic service timeline, not a transmitted RF waveform.

    Source start/payload never enter this decision. Air deadline is estimated
    from decoded timing. A separate scoreboard may compare it to source truth.
    """
    from selected_rf import validate_rf_configuration_identity
    validate_rf_configuration_identity(environment)
    validate_contract_provenance(contract,environment.get('design_provenance'))
    control_hz=packet_control_clock(environment)
    context={key:deepcopy(environment[key]) for key in ('design_provenance','resolved_configuration',
        'scenario_overrides','scenario_assumptions','operating_conditions') if key in environment}
    context['model_role']='external_fpga_response_policy_and_service_bound'
    context['control_counter_hz']=control_hz
    if not all(math.isfinite(v) and v>=0 for v in (fpga_work_s,analog_settle_s,conversion_latency_s)):
        raise ValueError('Finite nonnegative processing and settling budgets required')
    if host_samples_ready_s is not None and (not math.isfinite(host_samples_ready_s) or host_samples_ready_s<0):raise ValueError('Finite nonnegative host availability required')
    decoded=bytes.fromhex(observation.get('pdu_hex',''))
    accepted=(observation.get('crc_ok',False) and len(decoded)==14 and
              decoded[0]&15==3 and decoded[0]&0x80 and decoded[1]==12 and decoded[8:14]==advertiser_address)
    if not accepted:return dict(context,request_accepted=False,reply_armed=False,reason='No valid addressed scan request')
    fs=settings['sample_hz']
    config=environment.get('resolved_configuration')
    if config is not None:
        if config['engine']!='rf' or not math.isclose(fs,config['sample_hz'],rel_tol=1e-12):
            raise ValueError('Response sample rate conflicts with resolved RF configuration')
    word=environment['host_spectrum']['d2h_word_hz']
    h2d=environment['host_spectrum']['h2d_word_hz']
    down=transport_service(contract,sample_hz=fs,word_hz=word)
    up=transport_service(contract,sample_hz=fs,word_hz=h2d)
    if not (down['rate_stable'] and up['rate_stable']):
        return dict(context,request_accepted=True,reply_armed=False,reason='Insufficient sustained sample service',
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
    if host_samples_ready_s is None:
        if conversion_latency_s:stage('complete_last_required_conversion',conversion_latency_s,'chip ADC')
        stage('deliver_last_required_samples',down['delay_bound_s'],'chip/host transport')
        stage('resampler_lookahead',32/fs,'FPGA')
    else:
        # Caller has actually delivered the finite record including FIR lookahead.
        # Do not charge conversion, transport and lookahead a second time.
        stage('wait_for_actual_host_record',max(0.,host_samples_ready_s-now),'observed chip/FPGA delivery')
    stage('CRC_address_policy_and_response_generation',fpga_work_s,'FPGA')
    stage('wait_for_command_frame',64/h2d,'host transport')
    transition=rf_transition_budget(before=settings,after=settings,operation='turnaround',
        epoch=7,host_word_hz=h2d,command_words=8,cdc_cycles=2,control_hz=control_hz,
        boundary_wait_s=64/word,analog_settle_s=analog_settle_s,source_lock_s=0.,
        host_training_words=0,fpga_recovery_s=0.,deadline_s=150e-6,d2h_lo_divider=32)
    for event in transition['events']:
        stage(event['state'],event['end_s']-event['start_s'],event['owner'])
    # Reserve room for the service-curve backlog as well as initial samples.
    # Keep the usual 32-sample prefill where it fits; adapt at faster sample
    # rates rather than silently requiring a larger on-chip FIFO.
    reserve=contract['transport']['scheduling']['ingress_bits_per_source']
    available_samples=max(0,(reserve-up['backlog_bound_bits'])//24)
    prefill_bits=min(32,available_samples)*24
    stage('response_sample_prefill',up['service_latency_s']+prefill_bits/up['guaranteed_service_bps'],'FPGA/host transport')
    service_fits=(down['rate_stable'] and up['rate_stable'] and
                  max(down['backlog_bound_bits'],prefill_bits+up['backlog_bound_bits'])<=reserve and
                  prefill_bits>=up['backlog_bound_bits'])
    ready=now
    armed=service_fits and ready<=target
    if armed:stage('wait_for_timestamped_launch',target-now,'generic timed action')
    return dict(context,request_accepted=True,reply_armed=armed,estimated_request_end_s=estimated_end,
        target_air_start_s=target,ready_s=ready,preparation_margin_s=target-ready,
        fpga_work_s=fpga_work_s,host_samples_ready_s=host_samples_ready_s,events=events,turnaround=transition,
        transport=dict(d2h=down,h2d=up,prefill_bits=prefill_bits,
            tx_prefill_plus_service_backlog_bits=prefill_bits+up['backlog_bound_bits'],comparison_storage_bits=reserve,
            sustained_service_and_storage_fit=service_fits),
        air_launch_timing_verified=False,reply_waveform_verified=False,
        scope='Scheduled readiness under assigned service bounds. RX timestamp calibration, DAC/filter launch delay, actual controls and TX settling/emissions remain unverified.')


def receiver_lna_gain(environment):
    """Selected legal LNA gain; primitive examples retain their 20 dB gain."""
    inventory=environment.get('receiver_parameters')
    if inventory is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound receiver requires LNA parameters')
        return 20.
    gains=inventory['lna']['gain_db']
    config=environment.get('resolved_configuration')
    gain=max(gains) if config is None else config['lna_gain_db']
    if gain not in gains:
        raise ValueError('Receiver LNA gain conflicts with design')
    return gain


def receiver_pga_peak(environment):
    """Resolve paired headroom; primitive examples retain their explicit 0.8 V law."""
    inventory=environment.get('receiver_parameters')
    if inventory is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound receiver requires PGA parameters')
        return .8
    i=inventory['pga_i']['differential_peak_limit_v']
    q=inventory['pga_q']['differential_peak_limit_v']
    if i!=q:
        raise ValueError('Paired receiver adapter requires matched I/Q PGA headroom')
    if not math.isfinite(i) or i<=0:
        raise ValueError('Positive finite PGA headroom required')
    return i


def receiver_pga_response(environment):
    """Shared physical response; unbound primitive fixtures retain their pole."""
    inventory=environment.get('receiver_parameters')
    if inventory is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound receiver requires PGA parameters')
        return .2e-6
    i=inventory['pga_i']['gain_response_tau_s']
    q=inventory['pga_q']['gain_response_tau_s']
    if i!=q or isinstance(i,bool) or not math.isfinite(i) or i<=0:
        raise ValueError('Matched positive finite PGA response times required')
    return i


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
                        blocker_dbm=-40.,blocker_attenuation_db=2.,blocker_modulation="cw",mixer_substeps=256,include_noise=True,
                        fpga_work_s=2e-6,noise_figure_db=None,adc_enob=None,
                        initial_gain_db=None,maximum_gain_db=None,gain_codes_db=None,thermal_noise_enabled=True,adc_noise_enabled=True,
                        rx_cutoff_hz=.7e6,blocker_offsets_hz=(2e6,),input_iip3_dbm=None,
                        converter_bits=None,aperture_rms_s=None,dynamic_rail=False,
                        sar_parameters=None,load_capture=None,lo_divider=None,
                        rx_filter_family='rx_all_pole_control',filter_initial_state=None,comparator_model=None):
    """Real packet RX through one declared rail/clock/reference environment.

    Wide internal envelope sampling resolves LO sidebands before analog filtering;
    only filtered values reach the actual divided-LO ADC clock. All gain control
    and packet decisions use received codes. RF source truth is scoreboard-only.
    """
    from converter_dynamics import validate_sar_binding
    from selected_rf import validate_rf_configuration_identity
    validate_rf_configuration_identity(environment)
    validate_contract_provenance(contract,environment.get('design_provenance'))
    control_hz=packet_control_clock(environment)
    validate_sar_binding(environment,sar_parameters,comparator_model=comparator_model)
    from selected_rf import selected_filter_cutoff,receive_supply_reference,receive_gain_elasticity,receive_supply_gain
    gain_reference_v=receive_supply_reference(environment,'gain_reference_v')
    gain_elasticity=receive_gain_elasticity(environment)
    headroom_reference_v=receive_supply_reference(environment,'headroom_reference_v')
    rx_cutoff_hz=selected_filter_cutoff(environment,'rx',rx_cutoff_hz,.7e6)
    pga_peak=receiver_pga_peak(environment)
    lna_gain=receiver_lna_gain(environment)
    inventory=environment.get('receiver_parameters')
    if inventory is None and (any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))):
        raise ValueError('Design-bound packet receiver requires receiver parameters')
    if inventory is not None:
        if inventory['adc_i']['native_bits']!=inventory['adc_q']['native_bits']:
            raise ValueError('Packet RX adapter requires matched I/Q native precision')
        if any(inventory[lane]['transport_bits']!=12 for lane in ('adc_i','adc_q')):
            raise ValueError('Packet RX adapter requires 12-bit transport words')
        if sar_parameters is None and inventory['adc_i']['enob_target']!=inventory['adc_q']['enob_target']:
            raise ValueError('Assigned-ENOB packet RX adapter requires matched I/Q ENOB targets')
    defaults=(dict(noise_figure_db=10.,adc_enob=8.,converter_bits=12,input_iip3_dbm=None) if inventory is None else
        dict(noise_figure_db=inventory['lna']['noise_figure_db'],adc_enob=inventory['adc_i']['enob_target'],
             converter_bits=inventory['adc_i']['native_bits'],input_iip3_dbm=inventory['lna']['iip3_dbm']))
    config=environment.get('resolved_configuration')
    if config is not None and (config['engine']!='rf' or config['direction']!='rx'):
        raise ValueError('Packet reception requires a resolved RF RX configuration')
    gains=None if inventory is None else sorted(set(inventory['pga_i']['gain_db']) & set(inventory['pga_q']['gain_db']))
    if gains is not None and not gains:
        raise ValueError('Packet RX requires a common I/Q PGA setting')
    default_initial=(config['pga_gain_db'] if config is not None else
        min(gains,key=lambda value:abs(value-39.)) if gains is not None else 40.)
    defaults.update(initial_gain_db=default_initial,maximum_gain_db=max(gains) if gains is not None else 60.,
        lo_divider=config['sample_divider'] if config is not None else 256)
    defaults['aperture_rms_s']=environment['adc_noise_parameters']['aperture_rms_s'] if inventory is not None else .3e-12
    supplied=dict(aperture_rms_s=aperture_rms_s,noise_figure_db=noise_figure_db,adc_enob=adc_enob,converter_bits=converter_bits,input_iip3_dbm=input_iip3_dbm,initial_gain_db=initial_gain_db,maximum_gain_db=maximum_gain_db,lo_divider=lo_divider)
    overrides={key:dict(selected=defaults[key],diagnostic=value) for key,value in supplied.items()
        if value is not None and value!=defaults[key]}
    aperture_rms_s=defaults['aperture_rms_s'] if aperture_rms_s is None else aperture_rms_s
    noise_figure_db=defaults['noise_figure_db'] if noise_figure_db is None else noise_figure_db
    adc_enob=defaults['adc_enob'] if adc_enob is None else adc_enob
    converter_bits=defaults['converter_bits'] if converter_bits is None else converter_bits
    if inventory is not None and converter_bits!=defaults['converter_bits']:
        raise ValueError('Packet ADC native width requires a changed design snapshot')
    if type(converter_bits) is not int:
        raise ValueError('Integer packet ADC native width required')
    input_iip3_dbm=defaults['input_iip3_dbm'] if input_iip3_dbm is None else input_iip3_dbm
    initial_gain_db=defaults['initial_gain_db'] if initial_gain_db is None else initial_gain_db
    maximum_gain_db=defaults['maximum_gain_db'] if maximum_gain_db is None else maximum_gain_db
    lo_divider=defaults['lo_divider'] if lo_divider is None else lo_divider
    if config is not None and (lo_divider!=config['sample_divider'] or environment['carrier_hz']!=config['reference_hz']):
        raise ValueError('Packet receive timing conflicts with resolved configuration')
    if config is not None and initial_gain_db!=config['pga_gain_db']:
        raise ValueError('Packet initial gain conflicts with resolved configuration')
    if gains is not None and (initial_gain_db not in gains or maximum_gain_db not in gains):
        raise ValueError('Packet receiver gain requires a supported setting or hypothetical design')
    context={key:deepcopy(environment[key]) for key in ('design_provenance','resolved_configuration',
        'scenario_overrides','scenario_assumptions','operating_conditions') if key in environment}
    context['receiver_diagnostic_overrides']=overrides
    if gains is not None:
        if gain_codes_db is not None and tuple(gain_codes_db)!=tuple(gains):
            raise ValueError('Gain code override conflicts with receiver inventory')
        gain_codes_db=tuple(gains)
    if sar_parameters is None and comparator_model is not None:
        raise ValueError('Comparator completion requires the selected SAR path')
    if environment['payload_engine']!='rf' or not math.isclose(environment['carrier_hz'],2.426e9):
        raise ValueError('This external channel-38 fixture requires an RF environment at 2426 MHz')
    if rx_filter_family not in ('rx_all_pole_control','rx_finite_zero'):
        raise ValueError('Supported generic RX transfer family required')
    if not dynamic_rail and (filter_initial_state is not None or rx_filter_family!='rx_all_pole_control'):
        raise ValueError('Explicit filter family/history requires the selected analog-filter path')
    if type(mixer_substeps) is not int or mixer_substeps not in (256,512,1024,2048,4096):
        raise ValueError('Resolved mixer refinement required')
    if (not math.isfinite(noise_figure_db) or noise_figure_db<0 or not math.isfinite(adc_enob) or
            converter_bits not in (10,12) or not 1<=adc_enob<=converter_bits or
            not math.isfinite(aperture_rms_s) or aperture_rms_s<0 or type(dynamic_rail) is not bool):
        raise ValueError('Finite NF, native resolution, ENOB and nonnegative aperture required')
    noise_factor=10**(noise_figure_db/10)
    if type(lo_divider) is not int or lo_divider not in (64,128,256,512):raise ValueError('Selected numeric LO divider required')
    lo=environment['carrier_hz'];fs=lo/lo_divider;observer_hz=10e6;source_hz=40e6
    settings=validate_rf_settings(sample_hz=fs,tx_cutoff_hz=1.5e6,rx_cutoff_hz=rx_cutoff_hz,
        rx_filter_order=5,sample_clock_source='external_lo',lo_hz=lo,lo_divider=lo_divider)
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
    if blocker_modulation not in ('cw','gfsk_prbs15'):
        raise ValueError('Unknown external blocker modulation')
    if blocker_dbm is not None:
        blocker_phase=0. if blocker_modulation=='cw' else reference_interferer_phase(times)
        blocker_w=1e-3*10**((blocker_dbm-blocker_attenuation_db)/10)
        for offset in blocker_offsets_hz:
            mixed+=math.sqrt(2*50*blocker_w)*np.exp(1j*(2*math.pi*(offset+cfo)*times+blocker_phase))
    nonlinearity=None
    if input_iip3_dbm is not None:
        mixed,nonlinearity=third_order_frontend(mixed,input_iip3_dbm)
    if 'local_load_response' in environment or 'periodic_clock' in environment:
        from selected_rf import DeliveredClock
        clock=DeliveredClock(environment)
    else:clock=PhaseNoise(tuple(environment['delivered_phase_tones']))
    if max(clock.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+max(blocker_offsets_hz)+abs(cfo)>=mix_hz/2:
        raise ValueError('Unresolved LO sidebands must not alias through the receive filter')
    mixed*=np.exp(-1j*clock.phase(times))
    # Fixed input-referred thermal PSD, before the analog filter. Complex
    # envelope power is E|z|²/(2R); noise factor and T=300.15 K are hypotheses.
    temperature_k=(sar_parameters.temperature_k if sar_parameters is not None else
                   environment['converter_parameters']['temperature_k'] if 'design_provenance' in environment else 300.15)
    noise_sigma=math.sqrt(50*1.380649e-23*temperature_k*noise_factor*mix_hz)
    if include_noise and thermal_noise_enabled:
        noise_rng=np.random.default_rng(seed+900)
        mixed+=noise_sigma*(noise_rng.normal(size=len(times))+1j*noise_rng.normal(size=len(times)))
    rail=environment['ledger']['local_payload_clock_core_rail_v']
    if dynamic_rail:
        from selected_rf import rail_at, analog_filter, rail_on_uniform_grid
        filtered=analog_filter(mixed*10**(lna_gain/20)*receive_supply_gain(rail_on_uniform_grid(environment,len(times),mix_hz),gain_reference_v,gain_elasticity),mix_hz,
            family=rx_filter_family,cutoff_hz=settings['rx_cutoff_hz'],initial_state=filter_initial_state)
    else:
        filtered=multipole_envelope(mixed*10**(lna_gain/20)*receive_supply_gain(rail,gain_reference_v,gain_elasticity),mix_hz,settings['rx_cutoff_hz'],settings['rx_filter_order'])
    filter_times=times+1/mix_hz
    ideal=np.arange(1,math.floor(duration*fs)+1)/fs
    actual=ideal+clock.crossing_error(ideal,lo)
    if include_noise:actual+=np.random.default_rng(seed+1800).normal(0,aperture_rms_s,len(actual))
    if np.any(np.diff(actual)<=0):raise ValueError('Nonmonotonic ADC timestamps')
    sampled=np.interp(actual,filter_times,filtered.real)+1j*np.interp(actual,filter_times,filtered.imag)
    from selected_rf import reference_at
    reference=reference_at(environment,actual)
    step=2/(1<<converter_bits)
    sigma=math.sqrt(max(0.,2**(2-2*adc_enob)-step**2)/12)
    noise_rng=np.random.default_rng(seed+1900)
    adc_noise=sigma*(noise_rng.normal(size=len(actual))+1j*noise_rng.normal(size=len(actual))) if include_noise and adc_noise_enabled else np.zeros(len(actual),complex)
    d2h=environment['host_spectrum']['d2h_word_hz'];h2d=environment['host_spectrum']['h2d_word_hz']
    service=transport_service(contract,sample_hz=fs,word_hz=d2h)
    agc_delay=service['delay_bound_s']+.5e-6+64/h2d+8/h2d+2/control_hz+1/fs
    converter=None;conversion_latency=0.
    if sar_parameters is None:
        codes,agc=bounded_gain_conversion(sampled,adc_noise,fs=fs,command_latency_s=agc_delay,
            gain_response_tau_s=receiver_pga_response(environment),gain_codes_db=gain_codes_db,
            reference_scale=reference,pga_peak_v=pga_peak*(rail_at(environment,actual) if dynamic_rail else rail)/headroom_reference_v,
            initial_gain_db=initial_gain_db,maximum_gain_db=maximum_gain_db,converter_bits=converter_bits)
    else:
        if converter_bits!=10 or not dynamic_rail:raise ValueError('Selected SAR requires native 10-bit and moving rails')
        from converter_dynamics import paired_sar,ObservedGain
        from selected_rf import rail_at,reference_at,prepared_supply_functions
        rail_sampler,reference_sampler=prepared_supply_functions(environment)
        beginning=actual-sar_parameters.acquisition_s
        starts=np.interp(beginning,filter_times,filtered.real)+1j*np.interp(beginning,filter_times,filtered.imag)
        control=ObservedGain(sample_hz=fs,command_latency_s=agc_delay,
            gain_response_tau_s=receiver_pga_response(environment),
            acquisition_s=sar_parameters.acquisition_s,initial_gain_db=initial_gain_db,
            maximum_gain_db=maximum_gain_db,gain_codes_db=gain_codes_db,
            headroom_start=pga_peak*rail_at(environment,beginning)/headroom_reference_v,
            headroom_end=pga_peak*rail_at(environment,actual)/headroom_reference_v)
        words,converter,load=paired_sar(sampled,starts,actual,
            reference_sampler,rail_sampler,
            parameters=sar_parameters,noise=include_noise and adc_noise_enabled,
            seed=seed+4900,input_control=control,comparator_model=comparator_model)
        codes=(words[:,0]+1j*words[:,1])/2048;agc=control.report()
        conversion_latency=converter['conversion_latency_s']
        if load_capture is not None:load_capture.update(load)
    trace=agc.pop('gain_db')
    agc.update(minimum_gain_db=min(trace),maximum_observed_gain_db=max(trace),final_gain_db=trace[-1])
    # Nominal code timestamps only: actual jitter/reference are NOT handed to
    # FPGA reconstruction. Lookahead is explicitly charged in response_budget.
    observer_times=np.arange(math.floor(ideal[-1]*observer_hz))/observer_hz
    observed=bandlimited_samples(codes,observer_times*fs-1,32,cutoff=min(1.,observer_hz/fs))
    observation=observe(observed,fs=observer_hz,channel=38)
    reply=response_budget(observation,settings,environment,contract,
        advertiser_address=advertiser,fpga_work_s=fpga_work_s,conversion_latency_s=conversion_latency)
    if reply['request_accepted']:
        reply['scoreboard_uncalibrated_end_error_s']=reply['estimated_request_end_s']-(start_s+len(bits)/1e6)
    peak=sum(t['clock_rail_voltage_peak_v'] for t in environment['host_spectrum']['tones'])
    load_rail=environment.get('local_load_response',{}).get('rail_v',np.array([0.]))
    voltage_interval=[rail-peak+float(min(load_rail)),rail+peak+float(max(load_rail))]
    return dict(context,control_counter_hz=control_hz,rf_receive_supply_parameters=dict(gain_reference_v=gain_reference_v,headroom_reference_v=headroom_reference_v,gain_supply_elasticity=gain_elasticity),lna_gain_db=lna_gain,pga_nominal_peak_limit_v=pga_peak,seed=seed,wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,blocker_modulation=blocker_modulation,
        blocker_attenuation_db=blocker_attenuation_db,wanted_insertion_loss_db=2.,
        blocker_offsets_hz=list(blocker_offsets_hz),frontend_nonlinearity=nonlinearity,
        settings=settings,rx_filter_family=rx_filter_family,
        filter_initial_state=filter_initial_state,source_start_s=start_s,source_packet_end_s=start_s+len(bits)/1e6,
        source_cfo_hz=cfo,mixer_hz=mix_hz,mixer_substeps=mixer_substeps,
        sample_count=len(codes),adc_crossing_rms_s=float(np.sqrt(np.mean((actual-ideal)**2))),
        thermal_noise_density_v2_per_hz=2*50*1.380649e-23*temperature_k*noise_factor,
        thermal_noise_temperature_k=temperature_k,
        noise_figure_db=noise_figure_db,adc_enob=adc_enob if converter is None else None,
        native_converter_bits=converter_bits,converter=converter,conversion_latency_s=conversion_latency,
        settings_precision_scope='Legacy settings.converter_bits is the 12-bit transport format here; native_converter_bits selects the physical transfer model.',
        aperture_rms_s=aperture_rms_s,dynamic_rail=dynamic_rail,
        thermal_noise_enabled=include_noise and thermal_noise_enabled,
        adc_noise_enabled=include_noise and adc_noise_enabled,
        include_noise=include_noise,gain_control=agc,observation=observation,
        correct_request=observation.get('pdu_hex')==pdu.hex(),response=reply,
        conservative_local_rail_interval_v=voltage_interval,
        linear_fixture_voltage_range_guaranteed=voltage_interval[0]>=2.5 and voltage_interval[1]<=3.6,
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


def packet_driver_bias(environment):
    """Shared driver allocation; legacy mathematical fixtures retain 28 mA."""
    if 'transmitter_parameters' in environment:
        value=environment['transmitter_parameters']['rfdriver']['bias_current_a']
    elif any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        raise ValueError('Inventory environment missing transmitter parameters')
    else:
        value=.028
    if isinstance(value,bool) or not math.isfinite(value) or value<=0:
        raise ValueError('Positive finite RF driver bias required')
    return value


def packet_dac_settings(environment,converter_bits=None,aperture_rms_s=None,dac_enob=None):
    """Resolve DAC allocation and record explicit numerical diagnostic overrides."""
    inventory=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    if inventory and 'transmitter_parameters' not in environment:
        raise ValueError('Design-bound packet DAC requires transmitter parameters')
    if inventory or 'transmitter_parameters' in environment:
        params=environment['transmitter_parameters']
        bits=params['dac_i']['native_bits']
        if bits!=params['dac_q']['native_bits']:
            raise ValueError('Paired DAC native widths differ')
        full_scale=params['dac_i']['differential_peak_v']
        if full_scale!=params['dac_q']['differential_peak_v']:
            raise ValueError('Paired DAC full-scale voltages differ')
        noise=environment['dac_noise_parameters']
        defaults=dict(converter_bits=bits,aperture_rms_s=noise['aperture_rms_s'],dac_enob=noise['enob'])
    else:
        full_scale=1.
        defaults=dict(converter_bits=12,aperture_rms_s=0.,dac_enob=8.)
    supplied=dict(converter_bits=converter_bits,aperture_rms_s=aperture_rms_s,dac_enob=dac_enob)
    resolved={key:defaults[key] if value is None else value for key,value in supplied.items()}
    if (inventory or 'transmitter_parameters' in environment) and resolved['converter_bits']!=defaults['converter_bits']:
        raise ValueError('Packet DAC native width requires a changed design snapshot')
    if type(resolved['converter_bits']) is not int or resolved['converter_bits'] not in (10,12):
        raise ValueError('Supported integer packet DAC native width required')
    if not math.isfinite(resolved['dac_enob']) or not 1<=resolved['dac_enob']<=resolved['converter_bits']:
        raise ValueError('DAC ENOB must fit native precision')
    resolved['differential_peak_v']=full_scale
    overrides={key:dict(selected=defaults[key],diagnostic=value) for key,value in supplied.items()
               if value is not None and value!=defaults[key]}
    return resolved,overrides


def transmitted_scan_response(request,environment,contract,*,rx_timestamp_correction_s=0.,
                              tx_launch_advance_s=0.,host_gap_s=0.,mixer_substeps=256,
                              converter_bits=None,reconstruction_order=None,aperture_rms_s=None,dac_enob=None,
                              dynamic_rail=False,rf_bias_a=None,load_capture=None,
                              nominal_gain=None,pad_series_ohm=0.,rf_load=None,supply_gain_state=None):
    """Prepared FPGA reply -> finite FIFO -> actual DAC edges -> loaded RF -> peer.

    Source request end is used only in the returned scoreboard. Launch policy
    uses the decoded timestamp and explicit calibration values. The remote
    receiver has independent sample timing and sees no transmitted bits.
    """
    from selected_rf import validate_rf_configuration_identity
    validate_rf_configuration_identity(environment)
    validate_contract_provenance(contract,environment.get('design_provenance'))
    control_hz=packet_control_clock(environment)
    config=environment.get('resolved_configuration')
    if config is not None:
        if config['engine']!='rf' or config['direction']!='tx':
            raise ValueError('Packet transmission requires a resolved RF TX configuration')
        if config['reference_hz']!=environment['carrier_hz']:
            raise ValueError('TX carrier differs from resolved configuration')
        if 'settings' in request and not math.isclose(request['settings']['sample_hz'],config['sample_hz'],rel_tol=1e-12):
            raise ValueError('Reply sample rate differs from resolved TX configuration')
    driver_bias=packet_driver_bias(environment)
    params=environment.get('transmitter_parameters',{}).get('rfdriver')
    from selected_rf import tx_gain_reference
    gain_reference_v=tx_gain_reference(params,None)
    driver_defaults=(dict(nominal_gain=4.5,source_r_ohm_differential=40.,
        load_ohm_differential=50.,headroom_per_rail_v=.3) if params is None else params)
    output_parameters=environment['rf_output_parameters'] if params is not None else dict(TX_PARAMETERS)
    from selected_rf import configured_tx_gain
    selected_gain=driver_defaults['nominal_gain'] if config is None else configured_tx_gain(environment,nominal_gain)
    nominal_gain=selected_gain if nominal_gain is None else nominal_gain
    source_r=driver_defaults['source_r_ohm_differential']
    load_r=driver_defaults['load_ohm_differential']
    headroom=driver_defaults['headroom_per_rail_v']
    selected_rf_bias=(environment['inventory_current_a']['rf'] if 'inventory_current_report' in environment else .037)
    rf_bias_a=selected_rf_bias if rf_bias_a is None else rf_bias_a
    driver_overrides={key:dict(selected=selected,diagnostic=actual)
        for key,selected,actual in (('nominal_gain',selected_gain,nominal_gain),('rf_bias_a',selected_rf_bias,rf_bias_a))
        if selected!=actual}
    dac_settings,dac_overrides=packet_dac_settings(environment,converter_bits,aperture_rms_s,dac_enob)
    converter_bits=dac_settings['converter_bits'];aperture_rms_s=dac_settings['aperture_rms_s']
    dac_enob=dac_settings['dac_enob'];full_scale=dac_settings['differential_peak_v']
    context={key:deepcopy(environment[key]) for key in ('design_provenance','resolved_configuration',
        'scenario_overrides','scenario_assumptions','operating_conditions') if key in environment}
    context.update(dac_settings=dac_settings,dac_diagnostic_overrides=dac_overrides,
        driver_bias_current_a=driver_bias,driver_diagnostic_overrides=driver_overrides,rf_output_parameters=dict(output_parameters),
        driver_settings=dict(gain_reference_v=gain_reference_v,nominal_gain=nominal_gain,source_r_ohm=source_r,load_ohm=load_r,headroom_per_rail_v=headroom,rf_bias_a=rf_bias_a),
        configuration_scope='resolved' if 'resolved_configuration' in environment else
            'unresolved_environment_fixture')
    reply=request['response']
    if not reply['reply_armed']:
        return dict(context,transmitted=False,reason='Reply not armed',complete=False)
    from selected_rf import selected_filter_cutoff
    selected_filter_cutoff(environment,'tx',request['settings']['tx_cutoff_hz'],1.5e6)
    from selected_rf import selected_tx_filter
    bound='design_provenance' in environment
    selected_family,selected_order=selected_tx_filter(environment)
    if reconstruction_order is None:
        reconstruction_order=selected_order if bound else 1
    reconstruction_override=(dict(selected=selected_order,diagnostic=reconstruction_order)
        if bound and reconstruction_order!=selected_order else None)
    family={1:None,3:'tx_third_order',5:'rx_all_pole_control'}.get(reconstruction_order)
    context['reconstruction_diagnostic_override']=reconstruction_override

    if (not all(math.isfinite(x) and x>=0 for x in
                (rx_timestamp_correction_s,tx_launch_advance_s,host_gap_s,aperture_rms_s)) or
            mixer_substeps not in (256,512,1024,2048,4096) or converter_bits not in (10,12) or
            reconstruction_order not in (1,3,5) or type(dynamic_rail) is not bool):
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
    # Selected host-derived counter, or the explicit legacy 40 MHz fixture.
    trigger=math.ceil(desired*control_hz)/control_hz
    if reply['ready_s']>trigger:
        return dict(context,transmitted=False,reason='Prepared too late for corrected launch',complete=False)
    if 'local_load_response' in environment or 'periodic_clock' in environment:
        from selected_rf import DeliveredClock
        clock=DeliveredClock(environment)
    else:clock=PhaseNoise(tuple(environment['delivered_phase_tones']))
    begin=math.floor(reply['ready_s']*fs)-2
    end=math.ceil(trigger*fs)+count+8
    ideal=np.arange(begin,end)/fs
    edges=ideal+clock.crossing_error(ideal,lo)
    if aperture_rms_s:
        edges+=np.random.default_rng(request['seed']+3100).normal(0,aperture_rms_s,len(edges))
    prefill=reply['transport']['prefill_bits']//24
    # FPGA paces on the known consumption rate. Transport is a declared bounded
    # delay, not an instantaneous read from the full prepared FPGA waveform.
    arrivals=np.r_[np.full(prefill,reply['ready_s']),
        trigger+np.arange(1,count-prefill+1)/fs+reply['transport']['h2d']['delay_bound_s']+host_gap_s]
    played,queue=timed_dac_playback(codes,arrivals,edges,launch_s=trigger,
        depth_samples=contract['transport']['scheduling']['ingress_bits_per_source']//24,
        minimum_prefill_samples=prefill)
    if queue['first_consumption_s'] is None:
        return dict(context,transmitted=False,reason=queue['fault'],playback=queue,complete=False)
    launch=queue['first_consumption_s'];stop=queue['fault_time_s']
    if stop is None:stop=queue['last_consumption_s']+1/fs
    from selected_rf import reference_scale_at
    reference=reference_scale_at(environment,edges)
    rng=np.random.default_rng(request['seed']+3000)
    sigma=math.sqrt(max(0.,2**(2-2*dac_enob)-(2/(1<<converter_bits))**2)/12)
    native_dac_report=None
    if converter_bits==10:
        from selected_rf import native_dac
        words=np.rint(np.column_stack((played.real,played.imag))*2048).astype(np.int64)
        analog_codes,native_dac_report=native_dac(words,full_scale*reference)
        analog_codes+=sigma*(rng.normal(size=len(edges))+1j*rng.normal(size=len(edges)))*full_scale*reference
    else:
        analog_codes=(played+sigma*(rng.normal(size=len(edges))+1j*rng.normal(size=len(edges))))*full_scale*reference
    mix_hz=fs*mixer_substeps;window_start=trigger-4e-6
    native_step=environment.get('local_load_response',{}).get('native_source_step_s')
    if native_step is not None and mix_hz*native_step<1-1e-6:
        raise ValueError('TX observation must preserve native feedback sample resolution')
    if max(clock.maximum_offset_hz,environment.get('rail_maximum_offset_hz',0.))+request['settings']['tx_cutoff_hz']>=mix_hz/2:
        raise ValueError('Resolve delivered clock and rail modulation before TX observation')
    times=window_start+np.arange(math.ceil((count/fs+8e-6)*mix_hz))/mix_hz
    # Existing causal reconstruction filter; phase rotation remains on the same
    # absolute source realization used during the received request (no reset).
    if reconstruction_order in (3,5):
        from selected_rf import analog_hold_at
        reconstructed=analog_hold_at(analog_codes,edges,times,family=family,
            cutoff_hz=request['settings']['tx_cutoff_hz'])
        rf_times=times
    else:
        indices=np.searchsorted(edges,times,side='right')-1
        held=analog_codes[np.clip(indices,0,len(edges)-1)]
        reconstructed=multipole_envelope(held,mix_hz,request['settings']['tx_cutoff_hz'],1)
        rf_times=times+1/mix_hz
    rail=environment['ledger']['local_payload_clock_core_rail_v']
    gain=nominal_gain*rail/gain_reference_v
    if dynamic_rail:
        from selected_rf import rail_on_uniform_grid
        evaluated_rail=rail_on_uniform_grid(environment,len(rf_times),mix_hz,start_s=float(rf_times[0]))
        from selected_rf import tx_supply_gain
        instantaneous_gain=nominal_gain*tx_supply_gain(evaluated_rail,gain_reference_v,params,rf_times,state=supply_gain_state)
    else:
        evaluated_rail=np.asarray([rail])
        from selected_rf import tx_supply_gain
        instantaneous_gain=nominal_gain*tx_supply_gain(evaluated_rail,gain_reference_v,params,rf_times[:1],state=supply_gain_state)
    evaluated_supply_interval=[float(np.min(evaluated_rail)),float(np.max(evaluated_rail))]
    evaluated_supply_valid=evaluated_supply_interval[0]>=2.5 and evaluated_supply_interval[1]<=3.6
    opened=instantaneous_gain*output_envelope(reconstructed,np.exp(1j*clock.phase(rf_times)),**output_parameters)
    # Normal mute has finite slew after completion; fault mute remains an
    # explicit abrupt stress hypothesis, not physical isolation evidence.
    from selected_rf import output_enable_envelope
    gate=output_enable_envelope(rf_times,launch,stop,fault=queue['fault'] is not None)
    opened*=gate
    port=rf_tx_resistive_port(opened,source_resistance_ohm=source_r+pad_series_ohm,load_resistance_ohm=load_r)
    emitted=port['envelope_v']
    if load_capture is not None:
        load_capture.update(times_s=rf_times,normalized_output_power=np.minimum(abs(opened/1.2)**2,1.))
    electrical=rf_tx_compliance_budget(peak_open_v=float(np.max(abs(opened))),
        minimum_supply_v=evaluated_supply_interval[0],total_rail_bias_a=rf_bias_a,
        source_resistance_ohm=source_r+pad_series_ohm,load_resistance_ohm=load_r,driver_bias_current_a=driver_bias,
        peak_current_limit_a=driver_bias,headroom_per_rail_v=headroom,differential=True)
    reactive_report=None
    if rf_load is not None:
        from selected_rf import rf_pad_waveform
        network=rf_pad_waveform(opened,mix_hz,lo,driver_r_ohm=source_r,pad_series_ohm=pad_series_ohm,**dict(dict(load_ohm=load_r),**rf_load))
        current=np.maximum(abs(network['driver_current']),abs(network['driver_current_at_interval_start']))
        if np.any(current>driver_bias):raise ValueError('Narrowband reactive driver current exceeds assigned bias')
        emitted=network['load_voltage'];port['load_power_w']=abs(emitted)**2/(2*rf_load.get('load_ohm',load_r))
        source_power=np.maximum(.5*np.real(opened*np.conj(network['driver_current'])),
            .5*np.real(opened*np.conj(network['driver_current_at_interval_start'])))
        electrical['checks']['peak_current']=bool(max(current)<=driver_bias)
        electrical['checks']['energy']=bool(max(source_power)<=electrical['minimum_driver_dc_power_w'])
        electrical['within_declared_compliance']=all(electrical['checks'].values())
        electrical['peak_driver_current_a']=float(max(current))
        reactive_report=dict(parameters=rf_load,peak_driver_current_a=float(max(current)),
            peak_pad_voltage_v=float(max(abs(network['pad_voltage']))),
            scope='Same causal held-envelope RF pad/bond/matching network as wideband TX. Assigned linear network, sampled compliance; no nonlinear reactive load stability proof.')
        rf_times=rf_times+1/mix_hz
    # Independent remote downconversion/filter/sampling: no shared-LO subtraction,
    # no local DAC timestamps and no payload-fitted phase or frequency correction.
    remote=multipole_envelope(emitted*np.exp(-2j*math.pi*request['source_cfo_hz']*rf_times),mix_hz,.7e6,5)
    peer_hz=10e6;peer_times=window_start+np.arange(math.floor((times[-1]-window_start)*peer_hz))/peer_hz+37e-9
    samples=np.interp(peer_times,rf_times+1/mix_hz,remote.real)+1j*np.interp(peer_times,rf_times+1/mix_hz,remote.imag)
    peer=observe(samples,fs=peer_hz,channel=38)
    # Diagnostic RF-envelope threshold only, not the standard's first-bit timing
    # definition. Peer acquisition includes its own path delay too.
    threshold=.5*.25*full_scale*gain*load_r/(source_r+pad_series_ohm+load_r)
    above=np.flatnonzero(abs(emitted)>=threshold)
    half_start=float(rf_times[above[0]]) if len(above) else None
    if peer['acquired']:peer['absolute_start_estimate_s']=float(peer_times[0]+peer['start_sample']/peer_hz)
    active=(rf_times>=launch)&(rf_times<min(stop,launch+len(bits)/1e6))
    return dict(context,transmitted=True,complete=False,nominal_gain=nominal_gain,pad_series_ohm=pad_series_ohm,
        reactive_load=reactive_report,mixer_input_complex_peak_v=float(max(abs(reconstructed))),playback=queue,dac_clipped_samples=dac_clips,
        supply_gain_state=None if supply_gain_state is None else dict(supply_gain_state),
        converter_bits=converter_bits,reconstruction_order=reconstruction_order,
        dac_enob=dac_enob,dac_diagnostic_overrides=dac_overrides,
        aperture_rms_s=aperture_rms_s,dynamic_rail=dynamic_rail,native_dac=native_dac_report,
        exact_nonuniform_reconstruction=reconstruction_order in (3,5),
        rx_timestamp_correction_s=rx_timestamp_correction_s,tx_launch_advance_s=tx_launch_advance_s,
        host_gap_s=host_gap_s,desired_launch_s=desired,control_trigger_s=trigger,
        first_dac_consumption_s=launch,rf_half_amplitude_start_s=half_start,
        control_counter_hz=control_hz,
        scoreboard_rf_half_amplitude_gap_s=None if half_start is None else half_start-request['source_packet_end_s'],
        peer=peer,peer_correct_response=peer.get('pdu_hex')==pdu.hex(),
        fpga_waveform_storage='Static scan-response samples can be prepared in FPGA memory before the request; no full-packet chip buffer',
        fpga_source_interpolator_taps=64,
        loaded_average_active_power_w=float(np.mean(port['load_power_w'][active])),
        loaded_peak_envelope_v=float(np.max(abs(emitted))),electrical=electrical,
        evaluated_supply_interval_v=evaluated_supply_interval,evaluated_supply_valid=evaluated_supply_valid,
        supply_observation_scope='Finite waveform-grid extrema including prelaunch and tail; no intersample or arbitrary-phase voltage guarantee',
        emission_bands=rf_emission_bands(emitted,mix_hz,load_ohm=load_r if rf_load is None else rf_load.get('load_ohm',load_r)),
        output_enable=dict(rise_tau_s=50e-9,normal_fall_s=20e-9,fault_abrupt=queue['fault'] is not None,
            mute_complete_s=stop if queue['fault'] is not None else stop+20e-9),
        phase_time_origin_reset=False,reference_scale_min=float(reference.min()),reference_scale_max=float(reference.max()),
        linear_fixture_voltage_range_guaranteed=request['linear_fixture_voltage_range_guaranteed'],
        air_launch_timing_qualified=False,
        scope='Loaded reply waveform and independent strong-signal peer under assigned driver, gate and host-service models. Envelope threshold is a diagnostic marker, not certified first-bit timing. No TX-load PDN feedback, physical switch transients, peer sensitivity, emissions mask or real bridge/command qualification.')


def campaign():
    """Standalone framing/AGC sensitivity with explicit simplified analog inputs."""
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
        scope='Standalone LE 1M framing/AGC fixture: fixed 10 MS/s, 12-bit quantization with assigned 8-bit ENOB noise, 10 dB NF and continuous 40–60 dB gain. These simplified inputs do not represent the selected native ADC/PGA allocation. Causal prefix acquisition. Ideal-gain control retained beside ADC-driven bounded AGC with assigned command latency, gain settling and PGA clipping. Early-stage compression, NF versus gain, phase transients and host service implementation unqualified; no full power/timing join, PER confidence or compliance.')


if __name__=='__main__':
    result=campaign()
    for cutoff in (.7e6,1.5e6):
        for wanted in (-65.,-80.,-90.):
            for blocker in (None,-40.):
                for mode,latency in (('ideal_per_case',None),('bounded_agc',2e-6),('bounded_agc',8e-6)):
                    rows=[r for r in result['cases'] if (r['cutoff_hz'],r['wanted_dbm'],r['blocker_dbm'],r['gain_mode'],(r['gain_control'] or {}).get('command_latency_s'))==(cutoff,wanted,blocker,mode,latency)]
                    print(cutoff,wanted,blocker,mode,latency,sum(r['correct_packet'] for r in rows),'/',len(rows))
