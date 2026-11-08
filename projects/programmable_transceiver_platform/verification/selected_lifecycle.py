"""Selected loaded-clock edges drive existing lifecycle presence/recovery logic."""
import hashlib
import json
import sys
import numpy as np
import baseline_envelope as b
sys.path.insert(0,str(b.P/'system_model/architecture_fast'))
from behavioral import BehavioralChip,Assumptions,ReferenceLossError,AnalogQualificationError
from selected_rf import DeliveredClock,receiver_pga_peak


from design_definition import load_design, Scenario, validate_contract_provenance


def converter_supply_window(contract):
    limits=contract['physical_services']['sar_timing']['startup']['model_supply_window_v']
    if len(limits)!=2 or not np.all(np.isfinite(limits)) or not 0<limits[0]<limits[1]:
        raise ValueError('Ordered positive converter supply model window required')
    return tuple(limits)


def converter_supply_acceptance(contract,observations):
    observations=np.asarray(observations,float)
    if observations.ndim!=2 or observations.shape[1]!=2 or not len(observations) or not np.all(np.isfinite(observations)):
        raise ValueError('Finite timestamp/supply observation pairs required')
    low,high=converter_supply_window(contract);times,values=observations.T
    invalid=(values<low)|(values>high)
    return dict(minimum_required_v=low,maximum_required_v=high,
        evaluated_interval_v=[float(values.min()),float(values.max())],evaluated_points=len(values),
        invalid_points=int(invalid.sum()),first_invalid_time_s=float(times[invalid].min()) if np.any(invalid) else None)


def selected_transport_assumptions(environment):
    """Resolve transport timing separately from electrical-spectrum approximations."""
    from design_definition import validate_transport_binding
    parameters=validate_transport_binding(environment)
    rates=environment['host_spectrum'] if parameters is None else parameters
    owned={} if parameters is None else dict(startup_s=parameters['startup_s'])
    return Assumptions(h2d_clock_scale=rates['h2d_word_hz']/312.5e6,
                       d2h_clock_scale=rates['d2h_word_hz']/312.5e6,**owned)


def wired_snapshot_service_check(contract,*,design=None):
    """Selected finite queue under clock mismatch; not a PCIe protocol test."""
    from dataclasses import replace
    from check_contract import operating_clock_ledger
    design=b.design_for_contract(contract,design)
    config=design.configure(engine="wire",direction="rx",reference_hz=2.5e9,host_divider=8)
    environment=b.configured_environment(config)
    assumptions=selected_transport_assumptions(environment)
    ledger=operating_clock_ledger(contract)['configurations']
    bound=next(r['selected_snapshot_d2h_service_bound'] for r in ledger if r['configuration']=='wire_reference_2500000000')
    depth=contract['transport']['scheduling']['ingress_bits_per_source']
    rows=[]
    source_limit=contract['transport']['source_fast_ppm'];host_limit=contract['transport']['host_slow_ppm']
    for source_ppm in (-source_limit,source_limit):
        for host_ppm in (-host_limit,host_limit):
            maxima=[]
            for phase in np.arange(8)/8:
                rate=250e6*(1+source_ppm/1e6)
                chip=BehavioralChip(replace(assumptions,source_clock_scale=1+source_ppm/1e6,
                    d2h_clock_scale=assumptions.d2h_clock_scale*(1+host_ppm/1e6)))
                chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
                chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
                source=lambda i:(i*73+19)&1023
                flow=chip.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=128,
                    depth_bits=depth,directions=('rx',),epoch=chip.epoch,
                    rx_source=source,rx_event_time=lambda i:(i+phase)/rate)
                assert flow['fault'] is None
                words=chip.stream['rx_words']
                assert words and words==[source(i) for i in range(len(words))]
                assert flow['maximum_bits']<=bound['backlog_bound_bits']<=depth
                assert flow['produced_bits']==flow['returned_bits']+flow['pending_bits']
                maxima.append(flow['maximum_bits'])
            rows.append(dict(source_ppm=source_ppm,d2h_ppm=host_ppm,
                maximum_queue_bits_by_eighth_sample_phase=maxima))
    stalled=BehavioralChip(replace(assumptions,source_clock_scale=1+source_limit/1e6,
        d2h_clock_scale=assumptions.d2h_clock_scale*(1-host_limit/1e6)))
    stalled.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    stalled.configure_transport('exclusive');stalled.start();stalled.advance(stalled.ready_at)
    overload=stalled.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=4,
        depth_bits=depth,directions=('rx',),epoch=stalled.epoch,rx_source=lambda i:(i*73+19)&1023,
        host_pause_frames=2)
    assert overload['fault']=='overflow'
    return dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=[],model_role="shared_design_with_ideal_framed_transport",
        startup_guard_s=assumptions.startup_s,queue_depth_bits=depth,
        queue_status=contract["transport"]["scheduling"]["fifo_budget_status"],
        service_bound=bound,cases=rows,frames_per_case=128,
        missed_service_control=dict(host_pause_frames=2,flow=overload,
            scope='Skipping the first two quota snapshots while the source runs exceeds the finite queue; this is not an allowed recurring-stall guarantee.'),
        maximum_observed_bits=max(max(r['maximum_queue_bits_by_eighth_sample_phase']) for r in rows),
        scope='32 selected BehavioralChip RX streams at 2.5 Gb/s with concrete words, declared ppm corners and eight initial phases. Same-frame snapshot scheduling, shared ingress planning queue and exact prefix checks. Conditional analytic bound covers the assigned source/service envelope; finite traces corroborate it rather than proving all phases. No PCIe electrical waveform, physical CDC, additional implementation staging, host stalls, TX or protocol qualification.')


def wired_tx_lifecycle(environment,monitor_edges,*,loss_window_s=(22e-6,23e-6)):
    """Shared wired TX with explicitly injected reference gap and zero prefill data."""
    config=environment.get("resolved_configuration")
    if config is None or config["engine"]!="wire" or config["direction"] not in ("tx","duplex"):
        raise ValueError("Wired TX lifecycle requires a shared TX configuration")
    if config["line_rate_bps"]!=2.5e9 or config["host_word_hz"]!=312.5e6:
        raise ValueError("Wired TX lifecycle fixture requires 2.5 Gb/s and /8 host timing")
    from copy import deepcopy
    from design_definition import validate_transport_binding
    validate_transport_binding(environment)
    context=deepcopy({key:environment[key] for key in (
        "design_provenance","resolved_configuration","scenario_overrides",
        "scenario_assumptions","operating_conditions") if key in environment})
    parameters=environment["transport_parameters"]
    depth=parameters["legacy_tx_queue_bits"]
    queue_status=parameters["queue_status"]
    if type(depth) is not int or depth<20:
        raise ValueError("Invalid shared TX queue capacity")
    prefill=depth//2
    gap_start,gap_end=loss_window_s
    if not np.isfinite([gap_start,gap_end]).all() or not 0<gap_start<gap_end:
        raise ValueError("Ordered positive injected clock gap required")
    chip=BehavioralChip(selected_transport_assumptions(environment));chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.configure_transport('exclusive');chip.attach_reference(monitor_edges)
    chip.start()
    begin=chip.ready_at+1e-6
    if begin>=gap_start:
        raise ValueError("Injected clock gap must follow startup and initial streaming")
    chip.advance(begin);clock=DeliveredClock(environment);records=[]
    for stage in ('before_loss','after_restart'):
        origin=chip.time;ideal=origin+np.arange(1,3001)/250e6
        events=ideal+clock.crossing_error(ideal,2.5e9)
        events=events[(events<gap_start)|(events>=gap_end)]-origin
        emitted=[]
        source=lambda index:(index*73+19)&1023
        args=dict(mode=1,source_hz=250e6,sample_bits=10,frames=16,
            directions=('tx',),tx_source=source,tx_prefill_bits=prefill,tx_prefill_value=0,depth_bits=depth,
            tx_word_observer=lambda time,word:emitted.append((time,word)),
            tx_event_time=lambda index:float(events[index]))
        flow=chip.transfer(epoch=chip.epoch,**args)
        actual=[(word>>bit)&1 for time,word in emitted for bit in range(10)]
        expected=[0]*prefill+[(source(i)>>bit)&1 for i in range(3000) for bit in range(10)]
        assert actual and actual==expected[:len(actual)]
        assert all(not gap_start<=time<gap_end for time,word in emitted)
        records.append(dict(model_role="shared_design_with_injected_clock_loss",
            scope="Legacy framed transport with ideal CDC and zero-data prefill; synthetic clock gap tests epoch recovery, not physical pad muting or oscillator recovery.",
            **deepcopy(context),
            startup_guard_s=chip.a.startup_s,transport_started_at_s=origin,
            transport_fixture=dict(queue_depth_bits=depth,prefill_bits=prefill,
                prefill_policy="half_capacity_floor_zero_data",queue_status=queue_status,
                injected_clock_gap_s=[gap_start,gap_end],initial_ready_wait_s=1e-6),stage=stage,emitted_words=len(emitted),fault=flow['fault'],
            payload_correct=True,last_emission_s=emitted[-1][0]))
        if stage=='before_loss':
            assert flow['fault']=='reference_lost'
            stale=chip.epoch;records[-1]['discarded']=chip.stop()
            chip.advance(gap_end+100e-9);chip.start();chip.advance(chip.ready_at)
            try:chip.transfer(epoch=stale,**args)
            except ValueError:pass
            else:raise AssertionError('Stale TX epoch accepted')
        else:assert flow['fault'] is None
    return records


def package_handover_screen(contract,*,design=None):
    """Incremental load-only handover; not a joined payload lifecycle verdict."""
    from scipy.signal import lsim
    from robustness_envelope import local_load_state_space,LocalLoadTransient
    from reference_input_probe import full
    design=b.design_for_contract(contract,design)
    phase_path=b.P/'evidence/internal-phase-bound.json'
    phase_bytes=phase_path.read_bytes()
    phase_report=json.loads(phase_bytes)
    for name,digest in phase_report['sources_sha256'].items():
        if hashlib.sha256((b.P/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Refresh internal_phase_bound.py before joining handover margins: '+name)
    rows=[]
    for label,return_l,die_esl in b.network_cases(design):
        scenario=Scenario().override(reason='Handover package comparison',
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
        rf=handover_environment(design,'rf',2.4e9,scenario=scenario)
        wire=handover_environment(design,'wire',2.5e9,scenario=scenario)
        network=rf['network'];system=local_load_state_space(network)
        comparisons=[]
        for frequency in np.geomspace(1e3,1e10,141):
            z=2j*np.pi*frequency
            reduced=((system.C@np.linalg.solve(z*np.eye(5)-system.A,system.B)+system.D)*z).item()
            nodes,_,_=full(frequency,network,[0,-1,0,1,0],0.,.2,False)
            exact=nodes[1]-nodes[3]
            comparisons.append(dict(frequency_hz=float(frequency),absolute_error_ohm=float(abs(reduced-exact)),
                                    relative_error=float(abs(reduced-exact)/abs(exact))))
        # Host DC allocation must stay fixed for a single local-load input to apply.
        assert rf['ledger']['host_node_current_a']==wire['ledger']['host_node_current_a']
        delta=wire['ledger']['local_branch_current_a']-rf['ledger']['local_branch_current_a']
        phase_cases=[next(row for row in phase_report['cases']
                         if row['network_case']==label and row['carrier_hz']==carrier
                         and row['local_feed_resistance_ohm']==design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['package_r'] and row['internal_pulse_scale']==1.)
                     for carrier in (2.4e9,2.5e9)]
        for row in phase_cases:
            if row.get('design_provenance')!=design.provenance():
                raise ValueError('Phase-bound evidence conflicts with handover design')
        # Subtract each mode's own DC before combining ripple with the continuous
        # load trajectory; adding absolute intervals would double-count DC drop.
        ac_intervals=[[v-env['ledger']['local_payload_clock_core_rail_v']
                       for v in row['headroom']['sourcewise_rail_interval_v']]
                      for row,env in zip(phase_cases,(rf,wire))]
        ac_union=[min(v[0] for v in ac_intervals),max(v[1] for v in ac_intervals)]
        dt=2e-9;times=np.arange(10001)*dt;transitions=[]
        for ramp in (20e-9,100e-9,1e-6):
            slope=np.zeros(len(times));count=round(ramp/dt)
            slope[1000:1000+count]=delta/ramp
            slope[5000:5000+count]=-delta/ramp
            _,reference_voltage,state=lsim(system,U=slope,T=times,interp=False)
            persistent=LocalLoadTransient(network)
            voltage=[]
            for index,time in enumerate(times):
                if index in (1000,5000):
                    persistent.ramp_to(float(time),delta if index==1000 else 0.,
                                       float(times[index+count]-time))
                voltage.append(persistent.advance(float(time)))
            voltage=np.asarray(voltage)
            np.testing.assert_allclose(voltage,reference_voltage,rtol=1e-8,atol=1e-10)
            np.testing.assert_allclose(persistent.state,state[-1],rtol=1e-8,atol=1e-10)
            # One continuous state trajectory; RF/wired selection never resets charge.
            assert abs(state[-1,4])<1e-12
            expected=wire['ledger']['local_payload_clock_core_rail_v']-rf['ledger']['local_payload_clock_core_rail_v']
            np.testing.assert_allclose(voltage[4999],expected,rtol=1e-4,atol=1e-6)
            combined=[float(rf['ledger']['local_payload_clock_core_rail_v']+min(voltage)+ac_union[0]),
                      float(rf['ledger']['local_payload_clock_core_rail_v']+max(voltage)+ac_union[1])]
            transitions.append(dict(quasistationary_ripple_plus_sampled_handover_interval_v=combined,
                quasistationary_fixture_screen_pass=combined[0]>=2.5 and combined[1]<=3.6,
                lower_margin_v=combined[0]-2.5,upper_margin_v=3.6-combined[1],
                persistent_state_matches_batch=True,ramp_s=ramp,load_increment_a=delta,
                minimum_load_only_rail_v=float(rf['ledger']['local_payload_clock_core_rail_v']+min(voltage)),
                maximum_load_only_rail_v=float(rf['ledger']['local_payload_clock_core_rail_v']+max(voltage)),
                wired_plateau_shift_v=float(voltage[4999]),expected_dc_shift_v=float(expected),
                residual_at_end_v=float(voltage[-1])))
        rows.append(dict(handover_context(design,[rf,wire]),scenario_overrides=scenario.record(),return_l_h=return_l,die_esl_h=die_esl,
            worst_relative_comparison=max(comparisons,key=lambda x:x['relative_error']),
            worst_absolute_comparison=max(comparisons,key=lambda x:x['absolute_error_ohm']),
            transitions=transitions))
    return dict(design_provenance=design.provenance(),phase_evidence_sha256=hashlib.sha256(phase_bytes).hexdigest(),
        combined_screen_scope='Union of phase-independent steady-mode ripple intervals (including board tolerance) added to sampled continuous load-only transition. DC drop counted once. Quasistationary screening assumption: periodic load spectrum changes without an additional network startup transient. No rigorous between-sample transient bound, old/new clock overlap, converter-current feedback or physical model qualification. Passing this screen does not prove a transition voltage guarantee.',
        cases=rows,frequency_samples=141,frequency_range_hz=[1e3,1e10],
        transition_start_s=[2e-6,10e-6],end_s=20e-6,grid_s=2e-9,
        scope='Load-only RF to wired to RF on one continuous multibranch state trajectory. Ramp times are assigned probes. Frequency samples compare the reduced network with the selected split-return network including passive differential input loading, not an exhaustive error bound. No host-harmonic phase change, active clock-source injection, converter state, cold startup, physical slew constraint or payload acceptance. Rail extrema are sampled and exclude switching ripple. This is a reuse screen, not full lifecycle closure.')


def handover_environment(design, mode, carrier, *, scenario=None):
    settings=dict(engine=mode,direction='rx' if mode=='rf' else 'tx',reference_hz=carrier)
    if mode=='rf':settings.update(sample_divider=64,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    else:settings['host_divider']=8
    config=design.configure(**settings)
    scenario=Scenario() if scenario is None else scenario
    return b.configured_environment(config,scenario)


HANDOVER_PHYSICAL_KEYS=('operating_conditions','reference_pad_parameters',
    'reference_package_parameters','reference_supply_parameters',
    'reference_acceptance_parameters','clock_input_configuration',
    'board_source_v','rf_receive_supply_parameters','wired_supply_gain_parameters',
    'control_hz','transport_parameters')


def handover_host_parameters(environment):
    source=b.host_source_parameters(environment)
    return {key:source[key] for key in ('output_voltage_v','output_cap_f',
        'd2h_internal_charge_c','internal_charge_c','d2h_word_hz','h2d_word_hz',
        'd2h_internal_tau_s','alternating','h2d_origin_s','external_return_fraction')}


def handover_context(design, environments):
    import copy
    from design_definition import validate_transport_binding
    conditions=[];overrides=[]
    for environment in environments:
        if environment.get('design_provenance')!=design.provenance():
            raise ValueError('Handover endpoint conflicts with shared design')
        validate_transport_binding(environment)
        conditions.append(copy.deepcopy({key:environment[key] for key in (
            'resolved_configuration','scenario_overrides','scenario_assumptions')+HANDOVER_PHYSICAL_KEYS}))
        conditions[-1]['host_source_parameters']=copy.deepcopy(handover_host_parameters(environment))
        if 'adc_switching' in environment:
            conditions[-1]['adc_switching']=copy.deepcopy(environment['adc_switching'])
        for override in environment['scenario_overrides']:
            if override not in overrides:overrides.append(copy.deepcopy(override))
    return dict(design_provenance=design.provenance(),
        resolved_configurations=[copy.deepcopy(env['resolved_configuration']) for env in environments],
        environment_conditions=conditions,scenario_overrides=overrides,probe_assumptions=dict(
            timing_mean_a=.010,core_mean_a=.020,core_event_hz=156.25e6,
            pulse_tau_s=.2e-9,harmonics=64,
            transition='Assigned finite-slew activity schedule; not demonstrated control circuitry'))


def switching_load_handover(contract,*,design=None):
    """Continuous local network with a smoothly changed periodic load spectrum."""
    from scipy.signal import lsim
    from robustness_envelope import local_load_state_space
    design=b.design_for_contract(contract,design)
    rf=handover_environment(design,'rf',2.4e9)
    wire=handover_environment(design,'wire',2.5e9)
    system=local_load_state_space(rf['network'])
    def tones(rate,environment):
        loads=[dict(owner='timing',mean_a=.010,event_hz=rate,tau_s=.2e-9,harmonics=64),
               dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
        return [(f,-ports[1]) for f,ports in b.internal_switching_sources(loads,owner_current_a=environment['inventory_current_a']).items()]
    old,new=tones(rf['carrier_hz']/16,rf),tones(wire['carrier_hz']/16,wire)
    initial=sum(np.real(np.linalg.solve(2j*np.pi*f*np.eye(5)-system.A,system.B[:,0])*(2j*np.pi*f*v)) for f,v in old)
    delta=wire['ledger']['local_branch_current_a']-rf['ledger']['local_branch_current_a']
    results=[];previous=None;previous_observer=None
    for dt in (25e-12,12.5e-12,6.25e-12):
        t=np.arange(round(.8e-6/dt)+1)*dt
        def waveform(items):
            value=np.zeros(len(t));derivative=value.copy()
            for f,v in items:
                wave=v*np.exp(2j*np.pi*f*t)
                value+=wave.real;derivative+=(2j*np.pi*f*wave).real
            return value,derivative
        a,da=waveform(old);z,dz=waveform(new)
        # Half-cosine crossfade conserves the assigned mean and has zero slope
        # at both ends. This is a generic activity schedule, not glitchless RTL.
        q=np.clip((t-.2e-6)/100e-9,0.,1.)
        blend=(1-np.cos(np.pi*q))/2
        derivative=np.where((q>0)&(q<1),np.pi*np.sin(np.pi*q)/(200e-9),0.)
        current=(1-blend)*a+blend*z+delta*blend
        # ZOH slope is the exact derivative of the piecewise-linear current.
        # This avoids accumulated load-charge drift from sampling dI/dt.
        exact_slope=(1-blend)*da+blend*dz+derivative*(z-a+delta)
        slope=np.r_[np.diff(current)/dt,exact_slope[-1]]
        _,v,state=lsim(system,U=slope,T=t,X0=initial,interp=False)
        np.testing.assert_allclose(state[:,4],current,rtol=0,atol=1e-10)
        rail=rf['ledger']['local_payload_clock_core_rail_v']+v
        # Smooth-source observation uses the analytical instantaneous slew.
        # State remains the numerical piecewise-linear approximation.
        observed=rail+system.D.item()*(exact_slope-slope)
        result=dict(smooth_source_observed_interval_v=[float(min(observed)),float(max(observed))],
                    grid_s=dt,samples=len(t),sampled_rail_interval_v=[float(min(rail)),float(max(rail))],
                    integrated_current_error_a=float(max(abs(state[:,4]-current))))
        if previous is not None:
            result['coarse_fine_maximum_rail_difference_v']=float(max(abs(previous-rail[::2])))
            result['smooth_source_coarse_fine_difference_v']=float(max(abs(previous_observer-observed[::2])))
        previous=rail;previous_observer=observed
        results.append(result)
    return dict(handover_context(design,[rf,wire]),cases=results,load_increment_a=delta,transition_start_s=.2e-6,transition_duration_s=100e-9,
        initial_state='Settled RF periodic local-load state, including stored energy and ripple; no reset at mode change.',
        scope='Selected reduced local-load network with 64-harmonic timing/core currents and the shared-inventory DC handover on one causal trajectory. Assigned half-cosine spectrum crossfade; 25/12.5/6.25 ps refinement. Smooth-source observer corrects direct slew feedthrough only; numerical circuit state is unchanged. Raw piecewise-linear observations retained. No host-port or external-clock forcing, converter loads, independent phase sweep, board tolerance or physical control qualification. Sampled rail extrema are not full-chip voltage guarantees.')


def full_package_handover(contract,*,adc_current_a=0.,reverse=False,rf_retune=False,capture=None,design=None):
    """Periodic ports on one transition; ADC None selects its full allocation."""
    from reference_input_probe import package_descriptor,PackageTransient,reference_capacitance,reference_passive_parameters
    design=b.design_for_contract(contract,design)
    clock_threshold_v=design.architecture['model_assumptions']['reference_input_acceptance']['parameters']['threshold_v']
    reference_parameters=design.architecture['blocks']['refbuf']['parameters']
    reference_target=reference_parameters['target_v']
    reference_gain=reference_target*reference_parameters['supply_fraction_per_v']
    reference_pole=reference_parameters['supply_pole_hz']
    environments=[handover_environment(design,mode,carrier)
                  for mode,carrier in [('rf',2.4e9),('wire',2.5e9)]]
    if rf_retune:
        if reverse:raise ValueError('RF retune and reverse handover are separate cases')
        environments[1]=handover_environment(design,'rf',2.484e9)
    if reverse:environments.reverse()
    config=contract['physical_services']['external_clock_input'];opts=config['input_model']
    matrices=package_descriptor(environments[0]['network'],mismatch=opts['mismatch'],opposed=opts['opposed'],
        **reference_passive_parameters(environments[0]))
    E,G,F=matrices;waveforms=[]
    for env in environments:
        if env['payload_engine']=='rf':env['adc_switching']=dict(sample_hz=env['resolved_configuration']['sample_hz'],mean_a=b.adc_pair_current_allocation(env) if adc_current_a is None else adc_current_a,pulse_tau_s=.2e-9,harmonics=128)
    for env in environments:
        carrier=env['carrier_hz']
        env['internal_switching_loads']=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
            dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
        tones={f:np.r_[v,0j,0j] for f,v in b.partitioned_host_sources(env).items()}
        mismatch=opts['mismatch'];skew=config['source_leg_skew_s'];w=2*np.pi*carrier
        vs=config['source_differential_peak_v']/2*np.array([(1+mismatch/2)*np.exp(.5j*w*skew),-(1-mismatch/2)*np.exp(-.5j*w*skew)])
        tones[carrier]=tones.get(carrier,np.zeros(7,complex))+np.r_[np.zeros(5),vs]
        waveforms.append(tones)
    # Keep H2D/core activity alive while LO-derived D2H/timing stops.
    common_env=dict(environments[0],internal_switching_loads=[dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)])
    common_env.pop('adc_switching',None)  # RF ADC must not leak into the persistent H2D/core group.
    common={f:np.r_[v,0j,0j] for f,v in b.partitioned_host_sources(common_env).items()}
    for f,vector in b.partitioned_d2h_sources(common_env).items():
        common[f]-=np.r_[vector,0j,0j]
    initial_phasors=[(f,np.linalg.solve(2j*np.pi*f*E+G,F@v)) for f,v in waveforms[0].items()]
    initial=sum(v.real for f,v in initial_phasors)
    delta=environments[1]['ledger']['local_branch_current_a']-environments[0]['ledger']['local_branch_current_a']
    rows=[];previous=None
    for dt in (12.5e-12,6.25e-12):
        times=np.arange(round(.8e-6/dt)+1)*dt
        drives=[]
        for tones in waveforms:
            u=np.zeros((len(times),7))
            for frequency,value in tones.items():
                u+=np.real(np.exp(2j*np.pi*frequency*times)[:,None]*value)
            drives.append(u)
        q=np.clip((times-.2e-6)/100e-9,0.,1.);blend=(1-np.cos(np.pi*q))/2
        common_drive=np.zeros_like(drives[0])
        for frequency,value in common.items():
            common_drive+=np.real(np.exp(2j*np.pi*frequency*times)[:,None]*value)
        def envelope(start):
            phase=np.clip((times-start)/20e-9,0.,1.)
            return (1-np.cos(np.pi*phase))/2
        old_gate=1-envelope(.2e-6);new_gate=envelope(.32e-6)
        assert not np.any((old_gate>0)&(new_gate>0))
        inputs=common_drive+(drives[0]-common_drive)*old_gate[:,None]+(drives[1]-common_drive)*new_gate[:,None]
        inputs[:,1]-=delta*blend;inputs[:,3]+=delta*blend
        model=PackageTransient(matrices,initial,inputs[0]);nodes=np.empty((len(times),7));nodes[0]=initial[:7]
        for i in range(1,len(times)):nodes[i]=model.advance(float(times[i]),inputs[i])[:7]
        rail=environments[0]['ledger']['local_payload_clock_core_rail_v']+nodes[:,1]-nodes[:,3]
        legs=nodes[:,5:7]-nodes[:,3,None]
        effective=legs[:,0]-legs[:,1]+opts['cm_gain']*np.mean(legs,axis=1)
        gap=(times>=.24e-6)&(times<=.30e-6)
        crossings=(effective[:-1]<clock_threshold_v)&(effective[1:]>=clock_threshold_v)&gap[:-1]&gap[1:]
        row=dict(reference_gap_effective_peak_v=float(max(abs(effective[gap]))),
                 reference_gap_rising_crossings_at_20mv=int(np.count_nonzero(crossings)),
                 grid_s=dt,samples=len(times),sampled_rail_interval_v=[float(min(rail)),float(max(rail))],
                 sampled_input_leg_peak_v=np.max(abs(legs),axis=0).tolist())
        if previous is not None:row['coarse_fine_maximum_node_difference_v']=float(np.max(abs(previous-nodes[::2])))
        previous=nodes;rows.append(row)
    if capture is not None:
        from scipy.signal import lfilter
        from reference_input_probe import PeriodicPackageContinuation
        tail_tones=dict(waveforms[1])
        tail_tones[0.]=np.array([0.,-delta,0.,delta,0.,0.,0.])
        tail=PeriodicPackageContinuation(matrices,model.state,tail_tones,time=float(times[-1]))
        capture.update(handover_context(design,environments))
        capture['package_continuation']=tail
        from converter_dynamics import adc_switching_sources
        # Continue exactly the ADC forcing used during the handover. A wired
        # endpoint has no ADC forcing; an RF endpoint must provide its inputs.
        endpoint=environments[1]
        adc_tones={} if endpoint['payload_engine']!='rf' else {
            f:np.r_[v,0j,0j] for f,v in adc_switching_sources(
                **endpoint['adc_switching'],
                parameters=b.environment_converter_parameters(endpoint)).items()}
        capture['clock_forcing']=dict(on=tail_tones,off={**common,0.:tail_tones[0.]},adc=adc_tones,carrier_hz=environments[1]['carrier_hz'],dc_rail_v=environments[0]['ledger']['local_payload_clock_core_rail_v'])
        ripple=nodes[:,1]-nodes[:,3]
        def filtered(pole):
            alpha=np.exp(-2*np.pi*pole*dt)
            start=sum(((v[1]-v[3])/(1+1j*f/pole)).real for f,v in initial_phasors)
            return lfilter([1-alpha],[1,-alpha],ripple,zi=[alpha*start])[0]
        capture.update(times_s=times,rail_v=rail,effective_input_v=effective,
            reference_v=reference_target+reference_gain*filtered(reference_pole),
            delay_s=config['supply_sensitivity_ps_per_mv']*1e-9*filtered(config['supply_delay_pole_hz']))
    continuation=None if capture is None else dict(initial_stored_state_residual=tail.initial_residual,
        algebraic_node_adjustment_v=tail.algebraic_node_adjustment_v,
        natural_node_residual_at_20us_v=float(np.max(abs(tail.evaluate([20e-6])[0,:7]-tail.particular(np.array([20e-6]))[0,:7]))),
        scope='Fixed final periodic forcing after 0.8 us; stored charge/flux retained. Algebraic node correction changes polygonal source interpolation to analytic tones. No converter recharge or readiness qualification on this tail.')
    return dict(handover_context(design,environments),periodic_continuation=continuation,direction='rf_retune' if rf_retune else 'wired_to_rf' if reverse else 'rf_to_wired',rf_adc_switching_mean_a=next(env['adc_switching']['mean_a'] for env in environments if 'adc_switching' in env),adc_scope='RF-only assigned periodic ADC switching follows RF-derived activity on shutdown or restart. Full CORE DC allocation remains reserved in both modes; ADC conversion state and reference recharge are not executed on this trajectory.',cases=rows,reference_stop_ramp_s=[.2e-6,.22e-6],reference_restart_ramp_s=[.32e-6,.34e-6],
        gap_observation_window_s=[.24e-6,.30e-6],transition_start_s=.2e-6,transition_duration_s=100e-9,
        scope='Selected full passive network; simultaneous host/internal/reference forcing with one stored state. Reference/LO-derived timing/D2H stop over 20 ns, remain off for 100 ns, then restart over 20 ns. H2D/core forcing continues. DC follows the endpoint ledgers over 100 ns (no mean change for RF retuning). Prescribed finite-slew envelopes, not measured oscillator or clock-gate behavior. Gap crossings are sampled analog threshold observations, not digital monitor qualification. Initial old-mode periodic steady state; nominal board voltage, fixed phases, no converter feedback or payload. 12.5/6.25 ps numerical comparison and sampled extrema only; no continuous-time or physical voltage guarantee.')


def analytic_clock_loss_segments(contract,capture,loss_at_s,restart_at_s,end_s):
    """Piecewise exact harmonic forcing, with retained passive natural modes."""
    from reference_input_probe import PeriodicPackageContinuation,ramped_tones
    tail=capture['package_continuation'];forcing=capture['clock_forcing']
    duration=20e-9;completion=contract['physical_services']['sar_timing']['maximum_conversion_s']
    times=sorted(set([loss_at_s,loss_at_s+completion,loss_at_s+duration,
        loss_at_s+completion+duration,restart_at_s,restart_at_s+duration,end_s]))
    assert times[0]==loss_at_s and times[-1]==end_s
    frequencies=set(forcing['on'])|set(forcing['off'])|set(forcing['adc'])
    clock={f:forcing['on'].get(f,np.zeros(7))-forcing['off'].get(f,np.zeros(7))-forcing['adc'].get(f,np.zeros(7)) for f in frequencies}
    state=tail.evaluate([loss_at_s])[0];segments=[]
    for start,end in zip(times[:-1],times[1:]):
        tones={f:v.copy() for f,v in forcing['off'].items()}
        for group,stop in ((clock,loss_at_s),(forcing['adc'],loss_at_s+completion)):
            for begin,rising in ((stop,False),(restart_at_s,True)):
                additions=ramped_tones(group,start_s=begin,duration_s=duration,rising=rising,interval_time_s=(start+end)/2)
                for frequency,value in additions.items():tones[frequency]=tones.get(frequency,np.zeros(7,complex))+value
        model=PeriodicPackageContinuation((tail.E,tail.G,tail.F),state,tones,time=start)
        segments.append((start,end,model));state=model.evaluate([end])[0]
    return segments


def capture_context(design, captures, *, operation):
    """Keep recorded input conditions distinct from this operation's own settings."""
    import copy
    inputs={};contexts={}
    keys=('design_provenance','resolved_configuration','resolved_configurations',
          'scenario_overrides','scenario_assumptions','scenario_stimuli','lifecycle_stimuli',
          'operating_conditions','probe_assumptions','input_capture_context','filter_configuration','environment_conditions',
          'diagnostic_input_intervention','diagnostic_input_reason')
    for name,capture in captures.items():
        provenance=capture.get('design_provenance')
        if ('design_provenance' in capture and (not isinstance(provenance,dict) or not provenance)
                or provenance is None and any(key in capture for key in
                    ('resolved_configuration','resolved_configurations','environment_conditions'))):
            raise ValueError(f'{name} capture requires design provenance for {operation}')
        if provenance is not None and provenance!=design.provenance():
            raise ValueError(f'{name} capture conflicts with {operation} design')
        if provenance is not None:
            from check_contract import verify_reported_configuration
            if 'resolved_configuration' in capture:
                verify_reported_configuration(design,capture['resolved_configuration'])
            if 'resolved_configurations' in capture:
                records=capture['resolved_configurations']
                if not isinstance(records,(list,dict)) or not records:
                    raise ValueError(f'{name} capture requires nonempty endpoint configurations')
                if isinstance(records,dict) and any(not isinstance(key,str) or not key for key in records):
                    raise ValueError(f'{name} capture requires nonempty configuration names')
                for record in records.values() if isinstance(records,dict) else records:
                    verify_reported_configuration(design,record)
        inputs[name]='design_bound' if provenance is not None else 'unbound_numerical_fixture'
        contexts[name]={key:copy.deepcopy(capture[key]) for key in keys if key in capture}
    return dict(design_provenance=design.provenance(),input_capture_scope=inputs,
        input_capture_context=contexts,scenario_overrides=[])


def continuation_context(design, captures):
    return capture_context(design,captures,operation='continuation')


def package_clock_loss(contract,capture,*,loss_at_s=22e-6,restart_at_s=23e-6,capture_out=None,design=None):
    """Finite-slew clock failure from the retained post-retune package state."""
    design=b.design_for_contract(contract,design)
    clock_threshold_v=design.architecture['model_assumptions']['reference_input_acceptance']['parameters']['threshold_v']
    reference_parameters=design.architecture['blocks']['refbuf']['parameters']
    reference_target=reference_parameters['target_v']
    reference_gain=reference_target*reference_parameters['supply_fraction_per_v']
    reference_pole=reference_parameters['supply_pole_hz']
    context=continuation_context(design,{'package':capture})
    from reference_input_probe import PackageTransient,PeriodicPackageContinuation,linear_source_filter
    from behavioral import ReferencePresence
    if not capture['times_s'][-1]<loss_at_s<restart_at_s:
        raise ValueError('Clock fault must follow the captured retune')
    tail=capture['package_continuation'];forcing=capture['clock_forcing']
    endpoints=captured_endpoint_configurations(design,capture)
    endpoint=(design.configure(engine='rf',direction='rx',reference_hz=forcing['carrier_hz'],
        sample_divider=64,pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
        if endpoints is None else endpoints[1])
    if endpoint.engine!='rf' or endpoint.direction!='rx' or endpoint.reference_hz!=forcing['carrier_hz']:
        raise ValueError('Clock-loss endpoint conflicts with captured forcing')
    context['resolved_configuration']=endpoint.record()
    divider=endpoint.sample_divider
    matrices=(tail.E,tail.G,tail.F);config=contract['physical_services']['external_clock_input']
    opts=config['input_model'];rows=[];previous=None;previous_reference=None;previous_delay=None
    weights=np.zeros(18);weights[1]=1.;weights[3]=-1.
    gain=config['supply_sensitivity_ps_per_mv']*1e-9
    reference_before=tail.observer(weights,pole_hz=reference_pole,initial_output=(capture['reference_v'][-1]-reference_target)/reference_gain if reference_gain else 0.)
    delay_before=tail.observer(weights,pole_hz=config['supply_delay_pole_hz'],initial_output=capture['delay_s'][-1]/gain)
    completion_s=contract['physical_services']['sar_timing']['maximum_conversion_s']
    from converter_dynamics import parameters_from_inventory
    assert abs(completion_s-sum(parameters_from_inventory(design.architecture).bit_durations_s))<1e-18
    for dt in (12.5e-12,6.25e-12):
        times=loss_at_s+np.arange(round((restart_at_s+400e-9-loss_at_s)/dt)+1)*dt
        drives=[]
        for tones in (forcing['on'],forcing['off'],forcing['adc']):
            values=np.zeros((len(times),7))
            for frequency,phasor in tones.items():
                values+=np.real(np.exp(2j*np.pi*frequency*times)[:,None]*phasor)
            drives.append(values)
        def envelope(start):
            q=np.clip((times-start)/20e-9,0.,1.);return (1-np.cos(np.pi*q))/2
        gate=1-envelope(loss_at_s)+envelope(restart_at_s)
        adc_gate=1-envelope(loss_at_s+completion_s)+envelope(restart_at_s)
        inputs=drives[1]+(drives[0]-drives[1]-drives[2])*gate[:,None]+drives[2]*adc_gate[:,None]
        initial=tail.evaluate([loss_at_s])[0]
        # Local elapsed time avoids loss of relative timestep precision far
        # from zero; forcing and subsequent observations keep absolute phase.
        model=PackageTransient(matrices,initial,inputs[0])
        states=np.empty((len(times),18));states[0]=initial
        for index in range(1,len(times)):states[index]=model.advance(float(index*dt),inputs[index])
        nodes=states[:,:7];legs=nodes[:,5:7]-nodes[:,3,None]
        effective=legs[:,0]-legs[:,1]+opts['cm_gain']*np.mean(legs,axis=1)
        rail=forcing['dc_rail_v']+nodes[:,1]-nodes[:,3]
        quiet=(times>=loss_at_s+100e-9)&(times<=restart_at_s-100e-9)
        thresholds=[]
        for level in (clock_threshold_v,clock_threshold_v+.010):
            indices=np.flatnonzero((effective[:-1]<level)&(effective[1:]>=level))
            edges=times[indices]+(level-effective[indices])*(times[indices+1]-times[indices])/(effective[indices+1]-effective[indices])
            fault_times=[]
            # Check every configured divider residue. Prehistory establishes a
            # healthy monitor; it does not reset phase at the source failure.
            period=divider/forcing['carrier_hz']
            for residue in range(divider):
                first=(edges[0] if len(edges) else loss_at_s)+residue/forcing['carrier_hz']
                prefix=first-np.arange(5,0,-1)*period
                prefix=prefix[prefix<loss_at_s]
                observed=np.r_[prefix,edges[residue::divider]]
                monitor=ReferencePresence(observed,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
                monitor.armed_at=loss_at_s-1e-6
                fault=monitor.fault_between(loss_at_s,restart_at_s)
                if fault is None:raise AssertionError('Clock absence escaped monitor')
                fault_times.append(fault)
            thresholds.append(dict(threshold_v=level,raw_edges=len(edges),
                quiet_gap_crossings=int(np.count_nonzero((edges>=loss_at_s+100e-9)&(edges<=restart_at_s-100e-9))),
                all_divider_residues_detect_loss=True,divider_residue_count=divider,
                monitor_fault_interval_s=[float(min(fault_times)),float(max(fault_times))]))
        final=PeriodicPackageContinuation(matrices,model.state,forcing['on'],time=float(times[-1]))
        ripple=nodes[:,1]-nodes[:,3]
        reference_values=reference_target+reference_gain*linear_source_filter(ripple,step_s=dt,pole_hz=reference_pole,initial_output=float(reference_before(loss_at_s)))
        delay_values=gain*linear_source_filter(ripple,step_s=dt,pole_hz=config['supply_delay_pole_hz'],initial_output=float(delay_before(loss_at_s)))
        reference_after=final.observer(weights,pole_hz=reference_pole,initial_output=(reference_values[-1]-reference_target)/reference_gain if reference_gain else 0.)
        delay_after=final.observer(weights,pole_hz=config['supply_delay_pole_hz'],initial_output=delay_values[-1]/gain)
        if capture_out is not None:
            capture_out.update(context,times_s=times,rail_v=rail,effective_input_v=effective,
                reference_v=reference_values,delay_s=delay_values,package_continuation=final,
                loss_at_s=loss_at_s,source_off_at_s=loss_at_s+20e-9,restart_at_s=restart_at_s)
        continuity=dict(reference_start_difference_v=float(reference_values[0]-(reference_target+reference_gain*reference_before(loss_at_s))),
            delay_start_difference_s=float(delay_values[0]-gain*delay_before(loss_at_s)),
            reference_end_difference_v=float(reference_target+reference_gain*reference_after(times[-1])-reference_values[-1]),
            delay_end_difference_s=float(gain*delay_after(times[-1])-delay_values[-1]))
        assert max(abs(continuity[k]) for k in ('reference_start_difference_v','reference_end_difference_v'))<1e-12
        assert max(abs(continuity[k]) for k in ('delay_start_difference_s','delay_end_difference_s'))<1e-21
        row=dict(filtered_state_continuity=continuity,reference_target_interval_v=[float(min(reference_values)),float(max(reference_values))],
            supply_delay_interval_s=[float(min(delay_values)),float(max(delay_values))],grid_s=dt,samples=len(times),rail_interval_v=[float(min(rail)),float(max(rail))],
            quiet_gap_effective_peak_v=float(max(abs(effective[quiet]))),thresholds=thresholds,
            resumed_stored_state_residual=final.initial_residual,
            resumed_algebraic_node_adjustment_v=final.algebraic_node_adjustment_v,
            continuation_to_45us_finite=bool(np.all(np.isfinite(final.evaluate([45e-6])))))
        if previous is not None:row['coarse_fine_maximum_node_difference_v']=float(np.max(abs(previous-nodes[::2])))
        if previous_reference is not None:
            row['coarse_fine_maximum_reference_difference_v']=float(np.max(abs(previous_reference-reference_values[::2])))
            row['coarse_fine_maximum_supply_delay_difference_s']=float(np.max(abs(previous_delay-delay_values[::2])))
        previous=nodes;previous_reference=reference_values;previous_delay=delay_values;rows.append(row)
    agreement=all(a['raw_edges']==z['raw_edges'] and a['quiet_gap_crossings']==z['quiet_gap_crossings'] and a['monitor_fault_interval_s']==z['monitor_fault_interval_s'] for a,z in zip(rows[0]['thresholds'],rows[1]['thresholds']))
    # Independent harmonic solution distinguishes source interpolation error
    # from crossing-observation resolution without resetting passive state.
    segments=analytic_clock_loss_segments(contract,capture,loss_at_s,restart_at_s,restart_at_s+400e-9)
    input_weights=np.zeros(18);cm=opts['cm_gain']
    input_weights[5]=1+cm/2;input_weights[6]=-1+cm/2;input_weights[3]=-cm
    observer_segments=[]
    reference_state=float(reference_before(loss_at_s));delay_state=float(delay_before(loss_at_s))
    boundary_errors=[]
    for start,end,part in segments:
        reference_observer=part.observer(weights,pole_hz=reference_pole,initial_output=reference_state)
        delay_observer=part.observer(weights,pole_hz=config['supply_delay_pole_hz'],initial_output=delay_state)
        boundary_errors.append(max(abs(float(reference_observer(start))-reference_state),abs(float(delay_observer(start))-delay_state)))
        observer_segments.append((start,end,dict(effective_input_v=part.observer(input_weights),
            ripple_v=part.observer(weights),reference_ripple_v=reference_observer,delay_ripple_v=delay_observer)))
        reference_state=float(reference_observer(end));delay_state=float(delay_observer(end))
    def observe(name,at):
        at=np.asarray(at,float);out=np.full(at.shape,np.nan)
        for start,end,observers in observer_segments:
            mask=(at>=start)&(at<=end)
            if np.any(mask):out[mask]=observers[name](at[mask])
        if not np.all(np.isfinite(out)):raise ValueError('Observation outside analytic fault trajectory')
        return out
    analytic_rows=[];previous_roots=None
    for step in (12.5e-12,6.25e-12,3.125e-12):
        at=loss_at_s+np.arange(int((restart_at_s+400e-9-loss_at_s)/step)+1)*step
        observed=observe('effective_input_v',at)
        counts=[];threshold_roots=[]
        for threshold in (clock_threshold_v,clock_threshold_v+.010):
            indices=np.flatnonzero((observed[:-1]<threshold)&(observed[1:]>=threshold))
            low=at[indices].copy();high=at[indices+1].copy()
            for _ in range(16):
                middle=(low+high)/2
                above=observe('effective_input_v',middle)>=threshold
                high=np.where(above,middle,high);low=np.where(above,low,middle)
            roots=(low+high)/2;threshold_roots.append(roots)
            counts.append(dict(threshold_v=threshold,raw_edges=len(roots),
                quiet_gap_crossings=int(np.count_nonzero((roots>=loss_at_s+100e-9)&(roots<=restart_at_s-100e-9)))))
        root_error=None
        if previous_roots is not None and all(len(a)==len(z) for a,z in zip(previous_roots,threshold_roots)):
            root_error=max(float(np.max(abs(a-z),initial=0.)) for a,z in zip(previous_roots,threshold_roots))
        analytic_rows.append(dict(grid_s=step,thresholds=counts,maximum_refined_root_change_s=root_error))
        previous_roots=threshold_roots
    analytic_agrees=all(row['thresholds']==analytic_rows[0]['thresholds'] for row in analytic_rows[1:])
    final_time=float(at[-1]);final_part=segments[-1][2]
    final=PeriodicPackageContinuation(matrices,final_part.evaluate([final_time])[0],forcing['on'],time=final_time)
    if capture_out is not None:
        capture_out.update(context,times_s=at,rail_v=forcing['dc_rail_v']+observe('ripple_v',at),
            effective_input_v=observed,reference_v=reference_target+reference_gain*observe('reference_ripple_v',at),
            delay_s=gain*observe('delay_ripple_v',at),package_continuation=final,
            refined_raw_edges_s=threshold_roots[0],analytic_observe=observe,
            trajectory='analytic_half_cosine_retained_state',
            loss_at_s=loss_at_s,source_off_at_s=loss_at_s+20e-9,restart_at_s=restart_at_s)
    analytic=dict(cases=analytic_rows,grid_crossing_counts_agree=analytic_agrees,
        maximum_filter_boundary_error_v=max(boundary_errors),
        maximum_stored_state_residual=max(part.initial_residual for _,_,part in segments),
        maximum_algebraic_node_adjustment_v=max(part.algebraic_node_adjustment_v for _,_,part in segments),
        scope='Exact half-cosine sideband forcing and retained passive natural modes; three sampled observation grids. Selected converter forcing and refined roots use this analytic trajectory; host recovery remains separate. Grid agreement is not a proof excluding all grazing crossings or all-phase false edges.')
    return dict(context,analytic_ramp_comparison=analytic,selected_clock_trajectory='analytic_half_cosine_retained_state',trapezoidal_grid_clock_classification_agrees=agreement,numerical_clock_classification=('analytic_grid_agreement' if analytic_agrees else 'unresolved_analytic_grid_disagreement'),adc_completion_tail_s=completion_s,adc_activity_scope='Assigned periodic ADC activity envelope persists one maximum local conversion interval beyond reference shutdown. Extended activity envelope, not a rigorous worst-case bound or code-dependent final-conversion current; no extra DC charged.',grid_clock_classification_agrees=analytic_agrees,loss_at_s=loss_at_s,restart_at_s=restart_at_s,source_slew_s=20e-9,cases=rows,
        retained_package_initial_state=True,
        scope='Post-retune passive package state continued to 22 us, then actual differential source and derived timing/D2H drives ramp off and on; local ADC activity has an additional completion tail and H2D/core forcing stays active. All configured monitor-divider residues tested at two thresholds. Full planning DC remains reserved. This is the base linear package component: converter recharge overlay, in-flight conversion cancellation, missing D2H beats and actual payload recovery are not yet joined. No reset of stored passive energy; fixed phases, nominal board supply and assigned source ramps. Sampled crossings and an ideal prescaler do not qualify physical receiver noise/hysteresis or arbitrary-phase false-edge immunity.')


def clock_loss_sar_continuation(contract,base_capture,fault_capture,retune,retune_capture,*,extend_until_s=None,capture_out=None,design=None):
    """Retained converter and full-history recharge through source-off forcing."""
    design=b.design_for_contract(contract,design)
    clock_threshold_v=design.architecture['model_assumptions']['reference_input_acceptance']['parameters']['threshold_v']
    reference_parameters=design.architecture['blocks']['refbuf']['parameters']
    reference_target=reference_parameters['target_v']
    reference_gain=reference_target*reference_parameters['supply_fraction_per_v']
    reference_pole=reference_parameters['supply_pole_hz']
    context=continuation_context(design,dict(package=base_capture,fault=fault_capture,retune=retune,converter=retune_capture))
    endpoints=captured_endpoint_configurations(design,retune)
    if endpoints is not None:
        destination=endpoints[1]
        if destination.engine!='rf' or destination.direction!='rx':
            raise ValueError('SAR fault continuation requires an RF RX endpoint')
        for name,source in (('package',base_capture),('fault',fault_capture),('converter',retune_capture)):
            if 'resolved_configurations' in source and source['resolved_configurations']!=retune['resolved_configurations']:
                raise ValueError(f'{name} endpoint settings conflict with retained SAR')
            if 'resolved_configuration' in source and source['resolved_configuration']!=destination.record():
                raise ValueError(f'{name} endpoint settings conflict with retained SAR')
    from converter_dynamics import paired_sar,load_response,response_change
    tail=base_capture['package_continuation'];config=contract['physical_services']['external_clock_input']
    weights=np.zeros(18);weights[1]=1.;weights[3]=-1.
    gain=config['supply_sensitivity_ps_per_mv']*1e-9
    base_rail=tail.observer(weights)
    base_ref=tail.observer(weights,pole_hz=reference_pole,initial_output=(base_capture['reference_v'][-1]-reference_target)/reference_gain if reference_gain else 0.)
    base_delay=tail.observer(weights,pole_hz=config['supply_delay_pole_hz'],initial_output=base_capture['delay_s'][-1]/gain)
    weights=np.zeros(18);cm=config['input_model']['cm_gain'];weights[5]=1+cm/2;weights[6]=-1+cm/2;weights[3]=-cm
    base_input=tail.observer(weights)
    dc=base_capture['clock_forcing']['dc_rail_v'];frequency=base_capture['clock_forcing']['carrier_hz']
    t=fault_capture['times_s'];voltage=fault_capture['effective_input_v']
    prior=retune['converter_stages'][-1]
    if endpoints is None:
        environment=handover_environment(design,'rf',frequency)
    else:
        if destination.reference_hz!=frequency:
            raise ValueError('SAR fault endpoint conflicts with captured carrier')
        environments=captured_endpoint_environments(design,endpoints,
            base_capture,retune,retune_capture)
        if environments[0]['network']!=environments[1]['network']:
            raise ValueError('Retained recharge requires one common endpoint network')
        environment=environments[1]
    divider=environment['resolved_configuration']['sample_divider']
    host_divider=environment['resolved_configuration']['host_divider']
    context['resolved_configuration']=environment['resolved_configuration']
    p=b.environment_converter_parameters(environment)
    nominal=prior['sample_times_s'][-1]
    previous_response=retune_capture['response'];response=previous_response
    def overlay(name,q,source=None):
        source=response if source is None else source
        return np.interp(q,source['times_s'],source[name])
    low=nominal-.3/frequency;high=nominal+.3/frequency
    def prior_input(q):return base_input(q)+overlay('input_v',q,previous_response)
    assert high<t[0] and float(prior_input(low))<clock_threshold_v<float(prior_input(high))
    for _ in range(40):
        middle=(low+high)/2
        if float(prior_input(middle))>=clock_threshold_v:high=middle
        else:low=middle
    pre_root=(low+high)/2
    end_s=t[-1] if extend_until_s is None else extend_until_s
    if end_s<t[-1]:raise ValueError('Continuation cannot shorten captured fault')
    resumed=fault_capture['package_continuation']
    rail_weights=np.zeros(18);rail_weights[1]=1;rail_weights[3]=-1
    resumed_observers=dict(effective_input_v=resumed.observer(weights),
        ripple_v=resumed.observer(rail_weights),
        reference_ripple_v=resumed.observer(rail_weights,pole_hz=reference_pole,initial_output=(fault_capture['reference_v'][-1]-reference_target)/reference_gain if reference_gain else 0.),
        delay_ripple_v=resumed.observer(rail_weights,pole_hz=config['supply_delay_pole_hz'],initial_output=fault_capture['delay_s'][-1]/gain))
    def analytic(name,q):
        q=np.asarray(q,float);after=q>t[-1];out=np.empty(q.shape)
        if np.any(~after):out[~after]=fault_capture['analytic_observe'](name,q[~after])
        if np.any(after):out[after]=resumed_observers[name](q[after])
        return out
    iterations=[];previous_words=None;converged=False
    for iteration in range(4):
        effective=voltage+overlay('input_v',t)
        indices=np.flatnonzero((effective[:-1]<clock_threshold_v)&(effective[1:]>=clock_threshold_v))
        low=t[indices].copy();high=t[indices+1].copy()
        for _ in range(16):
            middle=(low+high)/2
            above=analytic('effective_input_v',middle)+overlay('input_v',middle)>=clock_threshold_v
            high=np.where(above,middle,high);low=np.where(above,low,middle)
        raw=(low+high)/2
        separation=(raw[0]-pre_root)*frequency;first_count=round(separation)
        assert first_count>0 and abs(separation-first_count)<.2
        counts=first_count+np.arange(len(raw))
        divided=raw[counts%divider==0]
        # The preceding run retains completed conversions only. Recover ADC
        # apertures before the fault trace whose conversions cross that boundary.
        bridge_counts=np.arange(divider,first_count,divider)
        bridge_nominal=pre_root+bridge_counts/frequency
        bridge_low=bridge_nominal-.3/frequency;bridge_high=bridge_nominal+.3/frequency
        def bridge_input(q):return base_input(q)+overlay('input_v',q)-clock_threshold_v
        if not (np.all(bridge_input(bridge_low)<0) and np.all(bridge_input(bridge_high)>0)):
            raise ValueError('Pre-fault ADC aperture lost its rising-edge bracket')
        for _ in range(32):
            middle=(bridge_low+bridge_high)/2;above=bridge_input(middle)>=0
            bridge_high=np.where(above,middle,bridge_high);bridge_low=np.where(above,bridge_low,middle)
        bridge_roots=(bridge_low+bridge_high)/2
        if np.any(bridge_roots>=t[0]):
            raise ValueError('Pre-fault aperture overlaps the captured fault roots')
        divided=np.r_[bridge_roots,divided]
        host_roots=raw[counts%host_divider==0]
        if end_s>t[-1]:
            tail_counts=np.arange(host_divider*(counts[-1]//host_divider+1),counts[-1]+int((end_s-raw[-1])*frequency),host_divider)
            nominal_tail=raw[-1]+(tail_counts-counts[-1])/frequency
            low=nominal_tail-.3/frequency;high=nominal_tail+.3/frequency
            assert np.all(low>t[-1])
            def tail_input(q):return analytic('effective_input_v',q)+overlay('input_v',q)-clock_threshold_v
            assert np.all(tail_input(low)<0) and np.all(tail_input(high)>0)
            for _ in range(24):
                middle=(low+high)/2;above=tail_input(middle)>=0
                high=np.where(above,middle,high);low=np.where(above,low,middle)
            tail_roots=(low+high)/2
            divided=np.r_[divided,tail_roots[tail_counts%divider==0]]
            host_roots=np.r_[host_roots,tail_roots]
        pre_fault=divided<t[0];base_sample_delay=np.empty_like(divided)
        base_sample_delay[pre_fault]=gain*base_delay(divided[pre_fault])
        base_sample_delay[~pre_fault]=gain*analytic('delay_ripple_v',divided[~pre_fault])
        samples=divided+base_sample_delay+overlay('delay_s',divided)
        samples=samples[samples+sum(p.bit_durations_s)<=end_s]
        def forcing(q,name,pre):
            q=np.asarray(q,float);before=q<t[0];values=np.empty(q.shape)
            if np.any(~before):
                if name=='rail_v':values[~before]=dc+analytic('ripple_v',q[~before])
                elif name=='reference_fraction':values[~before]=reference_target+reference_gain*analytic('reference_ripple_v',q[~before])
                else:raise ValueError(name)
            if np.any(before):values[before]=pre(q[before])
            return values+overlay(name,q)*(reference_target if name=='reference_fraction' else 1.)
        rail=lambda q:forcing(q,'rail_v',lambda x:dc+base_rail(x))
        reference=lambda q:forcing(q,'reference_fraction',lambda x:reference_target+reference_gain*base_ref(x))
        values=.3*np.exp(2j*np.pi*1e6*samples);starts=.3*np.exp(2j*np.pi*1e6*(samples-p.acquisition_s))
        words,report,trace=paired_sar(values,starts,samples,reference,rail,noise=True,
            initial_state=prior['final_state'],idle_step_s=1e-9,parameters=p)
        combined=dict(trace,segments=np.vstack((retune_capture['trace']['segments'],trace['segments'])),
            supply_observations=np.vstack((retune_capture['trace']['supply_observations'],trace['supply_observations'])))
        updated,load=load_response(combined,environment['network'],grid_s=retune['feedback_grid_s'],
            reference_input=b.reference_load_parameters(dict(environment,reference_load_parameters=dict(differential=config['input_model']))),
            sensitivity_ps_per_mv=config['supply_sensitivity_ps_per_mv'],dc_reference_a=p.reference_limit_a,reference_supply_parameters=reference_parameters,
            delay_pole_hz=config['supply_delay_pole_hz'],method='native_modal')
        rms,peak,rail_converged=response_change(updated,response)
        common=(updated['times_s']>=response['times_s'][0])&(updated['times_s']<=response['times_s'][-1])
        input_change=float(np.max(abs(updated['input_v'][common]-overlay('input_v',updated['times_s'][common]))))
        prefix=updated['times_s']<=prior['final_state']['end_time_s']
        prefix_error=float(np.max(abs(updated['rail_v'][prefix]-overlay('rail_v',updated['times_s'][prefix],previous_response))))
        # Held-current propagation removes FFT wraparound. Keep this gate:
        # boundary-straddling grid cells and clock iteration still need checks.
        prefix_valid=prefix_error<=1e-6
        stable=previous_words==words.tolist()
        grid_counts=[int(np.count_nonzero((effective[::stride][:-1]<clock_threshold_v)&(effective[::stride][1:]>=clock_threshold_v))) for stride in (4,2,1)]
        grid_agrees=len(set(grid_counts))==1
        converged=rail_converged and input_change<=1e-6 and stable and prefix_valid and grid_agrees
        iterations.append(dict(iteration=iteration,rail_rms_change_v=rms,rail_peak_change_v=peak,
            input_peak_change_v=input_change,frozen_prefix_rail_change_v=prefix_error,
            words_stable=stable,raw_edge_counts_by_grid=grid_counts,converged=converged,load=load))
        response=updated;previous_words=words.tolist()
        if converged:break
    completion=samples+sum(p.bit_durations_s)
    spans=(samples<fault_capture['source_off_at_s'])&(completion>fault_capture['source_off_at_s'])
    quiet=(samples>fault_capture['loss_at_s']+100e-9)&(samples<fault_capture['restart_at_s']-100e-9)
    # In-flight shutdown coverage depends on divider and phase. Record its
    # count; do not require every legal timing configuration to exercise it.
    assert not np.any(quiet)
    assert abs(report['reference_charge_balance_residual_c'])<1e-20
    if capture_out is not None:
        # Host divider inherits the same configured aperture anchor. Prefix clocks
        # are solved from the saved pre-fault feedback, never synthesized in
        # the missing-clock interval.
        prefix_counts=np.arange(-host_divider*int(2e-6*frequency/host_divider),first_count,host_divider)
        nominal_prefix=pre_root+prefix_counts/frequency
        nominal_prefix=nominal_prefix[nominal_prefix<t[0]-.3/frequency]
        low=nominal_prefix-.3/frequency;high=nominal_prefix+.3/frequency
        assert np.all(prior_input(low)<clock_threshold_v) and np.all(prior_input(high)>clock_threshold_v)
        for _ in range(24):
            middle=(low+high)/2;above=prior_input(middle)>=clock_threshold_v
            high=np.where(above,middle,high);low=np.where(above,low,middle)
        prefix_roots=(low+high)/2
        host_prefix=prefix_roots+gain*base_delay(prefix_roots)+overlay('delay_s',prefix_roots,previous_response)
        host_after=host_roots+gain*analytic('delay_ripple_v',host_roots)+overlay('delay_s',host_roots)
        combined['design_provenance']=design.provenance()
        capture_out.update(context,d2h_edges_s=np.r_[host_prefix,host_after],trace=combined,response=response)
    return dict(context,extension_scope='Fault interval enumerates sampled raw crossings on three grids; settled post-fault extension brackets only required host-clock roots and selects configured ADC apertures. Does not prove absence of every intervening or grazing raw crossing.',extended_until_s=float(end_s),feedback_grid_s=retune['feedback_grid_s'],numerical_feedback_converged=converged,feedback_iterations=iterations,clock_trajectory=fault_capture['trajectory'],samples=len(samples),sample_times_s=samples.tolist(),completion_times_s=completion.tolist(),words=words.tolist(),
        initial_state=prior['final_state'],final_state=trace['final_state'],converter=report,
        pre_fault_bridge_apertures=int(len(bridge_roots)),conversions_completing_after_source_fully_off=int(np.count_nonzero(spans)),quiet_gap_acquisitions=int(np.count_nonzero(quiet)),
        source='retained_sar_retune.extended_lifecycle.converter_stages.after.final_state',
        scope='Actual retained SAR charge and noise state consumes base package/reference/delay forcing through source loss and return. Local bit completion uses the selected allocated timing; divider phase counts observed roots across the gap. Known input tone; analog state is not reset by payload ownership. Full-history converter recharge overlays the analytic passive trajectory, retaining the previous charge/current history and shared reference-current reserve. Frozen-prefix grid error and iteration convergence are explicit; passive current propagation is causal, but this remains coupled waveform relaxation rather than a live converter solver. Any joined host STOP/recovery is reported separately in the attached transport result. Code-dependent non-reference activity, physical local sequencer qualification and protocol payload proof remain absent.')


def retained_sar_retune(contract,*,feedback_grid_s=.125e-9,package_capture=None,extend_until_s=None,supply_offset_v=0.,capture_out=None,design=None):
    from converter_dynamics import paired_sar,load_response,response_change,discharged_sar_state
    design=b.design_for_contract(contract,design)
    clock_threshold_v=design.architecture['model_assumptions']['reference_input_acceptance']['parameters']['threshold_v']
    reference_parameters=design.architecture['blocks']['refbuf']['parameters']
    reference_target=reference_parameters['target_v']
    reference_gain=reference_target*reference_parameters['supply_fraction_per_v']
    reference_pole=reference_parameters['supply_pole_hz']
    if package_capture is None:
        capture={};package=full_package_handover(contract,adc_current_a=None,rf_retune=True,capture=capture,design=design)
    else:package,capture=package_capture
    for source in (package,capture):
        if source.get('design_provenance') is not None and source['design_provenance']!=design.provenance():
            raise ValueError('Package capture conflicts with converter design')
    if not np.isfinite(supply_offset_v):raise ValueError('Finite supply offset required')
    direction=package['direction']
    if direction not in ('rf_retune','wired_to_rf'):raise ValueError('Converter continuation requires an RF destination')
    initial_engine='wire' if direction=='wired_to_rf' else 'rf'
    initial_carrier=2.5e9 if initial_engine=='wire' else 2.4e9
    final_carrier=capture['clock_forcing']['carrier_hz']
    endpoint_source=capture if 'resolved_configurations' in capture else package
    endpoints=captured_endpoint_configurations(design,endpoint_source)
    if endpoints is None and 'design_provenance' in capture:
        raise ValueError('Design-bound retune requires endpoint configurations')
    if endpoints is not None:
        records=endpoint_source['resolved_configurations']
        if 'resolved_configurations' in package and package['resolved_configurations']!=records:
            raise ValueError('Package and capture endpoint configurations conflict')
        if (endpoints[0].engine!=initial_engine or endpoints[1].engine!='rf'
                or endpoints[1].direction!='rx' or endpoints[1].reference_hz!=final_carrier):
            raise ValueError('Captured endpoint configuration conflicts with retune forcing')
        environment,destination=captured_endpoint_environments(design,endpoints,capture,package)
        if environment['network']!=destination['network']:
            raise ValueError('Retained recharge requires one common endpoint network')
    else:
        environment=handover_environment(design,initial_engine,initial_carrier)
        destination=handover_environment(design,'rf',final_carrier)
    before_divider=environment['resolved_configuration']['sample_divider'] if initial_engine=='rf' else 64
    after_divider=destination['resolved_configuration']['sample_divider']
    host_divider=destination['resolved_configuration']['host_divider']
    context=handover_context(design,[environment,destination])
    context['input_capture_scope']=('design_bound' if all(x.get('design_provenance') is not None for x in (package,capture)) else 'unbound_numerical_fixture')
    context['input_capture_context']=capture_context(design,{'package':package,'capture':capture},
        operation='converter')['input_capture_context']
    config=contract['physical_services']['external_clock_input']
    t=capture['times_s'];p=b.environment_converter_parameters(environment);response=None;previous_words=None;iterations=[]
    tail_observers={}
    if extend_until_s is not None:
        if not np.isfinite(extend_until_s) or extend_until_s<=t[-1]:raise ValueError('Extension must follow captured package transition')
        tail=capture['package_continuation'];weights=np.zeros(18);weights[1]=1.;weights[3]=-1.
        raw=tail.observer(weights)
        dc=environment['ledger']['local_payload_clock_core_rail_v']
        tail_observers['rail_v']=lambda q:dc+raw(q)
        ref=tail.observer(weights,pole_hz=reference_pole,initial_output=(capture['reference_v'][-1]-reference_target)/reference_gain if reference_gain else 0.)
        tail_observers['reference_v']=lambda q:reference_target+reference_gain*ref(q)
        gain=config['supply_sensitivity_ps_per_mv']*1e-9
        delay_observer=tail.observer(weights,pole_hz=config['supply_delay_pole_hz'],initial_output=capture['delay_s'][-1]/gain)
        tail_observers['delay_s']=lambda q:gain*delay_observer(q)
        cm=config['input_model']['cm_gain'];weights=np.zeros(18)
        weights[5]=1+cm/2;weights[6]=-1+cm/2;weights[3]=-cm
        tail_observers['effective_input_v']=tail.observer(weights)
    for iteration in range(4):
        def evaluate(name,feedback,q):
            q=np.asarray(q,float);values=np.interp(q,t,capture[name])
            if tail_observers:
                mask=q>t[-1]
                if np.any(mask):
                    values=np.asarray(values).copy();values[mask]=tail_observers[name](q[mask])
            if response is not None:values=values+np.interp(q,response['times_s'],response[feedback])*(reference_target if feedback=='reference_fraction' else 1.)
            values=values+supply_offset_v*dict(rail_v=1.,reference_v=reference_gain,delay_s=config['supply_sensitivity_ps_per_mv']*1e-9,effective_input_v=0.)[name]
            return values
        def forcing(name,feedback):
            return evaluate(name,feedback,t)
        voltage=forcing('effective_input_v','input_v');delay=forcing('delay_s','delay_s')
        rail_values=forcing('rail_v','rail_v');reference_values=forcing('reference_v','reference_fraction')
        indices=np.flatnonzero((voltage[:-1]<clock_threshold_v)&(voltage[1:]>=clock_threshold_v))
        edges=t[indices]+(clock_threshold_v-voltage[indices])*(t[indices+1]-t[indices])/(voltage[indices+1]-voltage[indices])
        raw_edges=edges.copy()
        edges+=np.interp(edges,t,delay)
        assert np.all(np.diff(edges)>0)
        before=edges[edges<.18e-6][before_divider::before_divider];after=edges[(edges>.4e-6)&(edges<.77e-6)][after_divider::after_divider]
        if tail_observers:
            raw_after=raw_edges[raw_edges>.4e-6]
            host_edges=edges[raw_edges>.4e-6][host_divider::host_divider]
            carrier=final_carrier
            next_index=host_divider*((len(raw_after)-1)//host_divider+1)
            indices_tail=np.arange(next_index,int((extend_until_s-.4e-6)*carrier),host_divider)
            nominal=raw_after[-1]+(indices_tail-(len(raw_after)-1))/carrier
            nominal=nominal[nominal+sum(p.bit_durations_s)<extend_until_s]
            low=nominal-.3/carrier;high=nominal+.3/carrier
            assert np.all(low>t[-1])
            def threshold(q):return evaluate('effective_input_v','input_v',q)-clock_threshold_v
            if not (np.all(threshold(low)<0) and np.all(threshold(high)>0)):
                raise ValueError('Continued divided-clock roots lost their rising-edge brackets')
            for step in range(32):
                middle=(low+high)/2;positive=threshold(middle)>=0
                high=np.where(positive,middle,high);low=np.where(positive,low,middle)
            raw_tail=(low+high)/2
            host_edges=np.r_[host_edges,raw_tail+evaluate('delay_s','delay_s',raw_tail)]
            sample_host_ratio=after_divider//host_divider
            if after_divider%host_divider:raise ValueError('Retained sampling requires integer host/sample divider ratio')
            after=host_edges[sample_host_ratio-1::sample_host_ratio]
            assert np.all(np.diff(host_edges)>0)
        assert len(before)>1 and len(after)>1
        state=discharged_sar_state(parameters=p);reports=[];segments=[];all_supply=[];all_words=[]
        rail=lambda q:evaluate('rail_v','rail_v',q)
        reference=lambda q:evaluate('reference_v','reference_fraction',q)
        for label,samples in (('before',before),('after',after)):
            if label=='before' and initial_engine=='wire':continue
            values=.3*np.exp(2j*np.pi*1e6*samples);starts=.3*np.exp(2j*np.pi*1e6*(samples-p.acquisition_s))
            words,report,trace=paired_sar(values,starts,samples,reference,rail,noise=True,initial_state=state,idle_step_s=1e-9,parameters=p)
            reports.append(dict(stage=label,samples=len(samples),first_sample_s=float(samples[0]),last_sample_s=float(samples[-1]),
                initial_state=state,final_state=trace['final_state'],converter=report,words=words.tolist(),sample_times_s=samples.tolist(),
                supply_acceptance=converter_supply_acceptance(contract,trace['supply_observations'])))
            state=trace['final_state'];segments.extend(trace['segments']);all_supply.extend(trace['supply_observations']);all_words.extend(words.tolist())
        combined=dict(trace,segments=np.asarray(segments),supply_observations=np.asarray(all_supply))
        updated,load=load_response(combined,environment['network'],grid_s=feedback_grid_s,
            reference_input=b.reference_load_parameters(dict(environment,reference_load_parameters=dict(differential=config['input_model']))),
            sensitivity_ps_per_mv=config['supply_sensitivity_ps_per_mv'],dc_reference_a=p.reference_limit_a,reference_supply_parameters=reference_parameters,
            delay_pole_hz=config['supply_delay_pole_hz'],method='native_modal')
        rms,peak,rail_converged=response_change(updated,response)
        input_change=None
        if response is not None:
            mask=(updated['times_s']>=response['times_s'][0])&(updated['times_s']<=response['times_s'][-1])
            input_change=float(max(abs(updated['input_v'][mask]-np.interp(updated['times_s'][mask],response['times_s'],response['input_v']))))
        words_stable=previous_words==all_words
        converged=rail_converged and input_change is not None and input_change<=1e-6 and words_stable
        iterations.append(dict(iteration=iteration,rail_rms_change_v=rms,rail_peak_change_v=peak,
            input_peak_change_v=input_change,words_stable=words_stable,load=load,converged=converged))
        response=updated;previous_words=all_words
        if converged:break
    if capture_out is not None:
        combined['design_provenance']=design.provenance()
        capture_out.update(context,trace=combined,response=response)
        if tail_observers:capture_out['d2h_edges_s']=host_edges
    return dict(context,direction=direction,final_carrier_hz=final_carrier,pre_transition_monitor_times_s=before.tolist(),initialization='Discharged SAR reference/sample/DAC charge at t=0 with already-powered, periodically loaded package; reference bias enabled immediately. This is converter cold initialization, not full chip power-up.',supply_offset_v=supply_offset_v,supply_offset_scope="Assigned local rail DC perturbation, with existing reference and delay sensitivities; source headroom/common-mode response is unqualified. Out-of-domain converter codes are diagnostic only.",extended_until_s=extend_until_s,extension_scope=('Fixed-source modal package tail and retained one-pole states; only divided-clock rising roots are searched. Recharge feedback spans the full extended conversion history.' if extend_until_s is not None else None),feedback_grid_s=feedback_grid_s,package=package,converter_stages=reports,feedback_iterations=iterations,numerical_feedback_converged=converged,
        scope='Full-package forcing and retained SAR across the declared RF retune or wired-to-RF transition; wired mode has no ADC apertures. Reference bias is enabled at time zero and remains allocated through the transition, with iterative reference-recharge feedback through the same passive network transfer. Shared reference-current recharge reserve replaces capture-mean subtraction; settled zero-recharge prehistory/tail assumed. Finite guarded FFT is not a live event solver. Sample edges include input and supply-delay feedback; deliberate guards exclude ramps/gap. Known baseband tone, not RF packet. Reference uses shared reference-buffer supply rejection and 1 ns idle substeps. Other ADC activity remains prescribed periodic current. No cold start, mid-bit stop, ready handshake, phase/package sweep or FPGA transport qualification.')


def lifecycle_tx_filter(design):
    """Resolve the retained TX filter and amplitude proof from one inventory."""
    from selected_rf import selected_tx_filter
    architecture=design.architecture
    return selected_tx_filter(dict(design_provenance=design.provenance(),
        filter_parameters={name:architecture['blocks'][name]['parameters']
            for name in ('txfilter_i','txfilter_q')}))


def lifecycle_filter_settings(design, rx_cutoff=None, tx_cutoff=None):
    """Resolve replay/lifecycle filter settings from the shared paired inventory."""
    from selected_rf import selected_filter_cutoff
    architecture=design.architecture
    environment=dict(design_provenance=design.provenance(),filter_parameters={
        name:architecture['blocks'][name]['parameters']
        for name in ('rxfilter_i','rxfilter_q','txfilter_i','txfilter_q')})
    return dict(rx_cutoff_hz=selected_filter_cutoff(environment,'rx',rx_cutoff,None),
                tx_cutoff_hz=selected_filter_cutoff(environment,'tx',tx_cutoff,None))


def captured_endpoint_environments(design, endpoints, *captures):
    """Restore typed physical scenarios consistently across retained captures."""
    from design_definition import PhysicalOverride
    conditions=None
    keys=('resolved_configuration','scenario_overrides','scenario_assumptions')
    for capture in captures:
        if 'environment_conditions' not in capture:continue
        rows=capture['environment_conditions']
        if not isinstance(rows,list) or len(rows)!=len(endpoints):
            raise ValueError('Captured endpoint conditions do not match endpoint count')
        current=[{key:row[key] for key in keys} for row in rows]
        if conditions is not None and current!=conditions:
            raise ValueError('Captured endpoint conditions conflict')
        conditions=current
    if conditions is None:
        if any(c.get('scenario_overrides') or c.get('scenario_assumptions') for c in captures):
            raise ValueError('Captured deviations require endpoint conditions')
        return [b.configured_environment(endpoint) for endpoint in endpoints]
    environments=[]
    for endpoint,condition in zip(endpoints,conditions):
        if condition['resolved_configuration']!=endpoint.record():
            raise ValueError('Captured conditions conflict with endpoint configuration')
        overrides=[]
        for item in condition['scenario_overrides']:
            if item['kind']!='physical_uncertainty':
                raise ValueError('Unsupported captured physical deviation')
            overrides.append(PhysicalOverride(item['parameter'],item['value'],item['reason']))
        scenario=Scenario(overrides=tuple(overrides),assumptions=condition['scenario_assumptions'])
        environments.append(b.configured_environment(endpoint,scenario))
    # Check each supplied condition record, not just the scenario selected above.
    # These are derived circuit inputs, not independent caller-owned overrides.
    physical_keys=HANDOVER_PHYSICAL_KEYS
    for capture in captures:
        if 'environment_conditions' not in capture:continue
        for environment,condition in zip(environments,capture['environment_conditions']):
            if condition.get('host_source_parameters')!=handover_host_parameters(environment):
                raise ValueError('Captured physical condition conflicts with shared endpoint: host_source_parameters')
            for key in physical_keys:
                if key not in condition or condition[key]!=environment[key]:
                    raise ValueError('Captured physical condition conflicts with shared endpoint: '+key)
    return environments


def captured_endpoint_configurations(design, capture):
    """Reconstruct saved settings; absent records identify an independent fixture."""
    if 'resolved_configurations' not in capture:
        if 'design_provenance' in capture:
            raise ValueError('Design-bound replay requires endpoint configurations')
        return None
    from check_contract import verify_reported_configuration
    records=capture['resolved_configurations']
    if not isinstance(records,list) or len(records)!=2:
        raise ValueError('Replay requires two endpoint configurations')
    return [verify_reported_configuration(design,record) for record in records]


def finite_sar_transport(contract,retune,*,design=None,rx_cutoff_hz=None,tx_cutoff_hz=None):
    """Replay observed words only, without extending the analog capture."""
    design=b.design_for_contract(contract,design)
    filters=lifecycle_filter_settings(design,rx_cutoff_hz,tx_cutoff_hz)
    rx_cutoff_hz=filters['rx_cutoff_hz'];tx_cutoff_hz=filters['tx_cutoff_hz']
    capture_provenance=retune.get('design_provenance')
    if capture_provenance is not None and capture_provenance!=design.provenance():
        raise ValueError('Converter capture conflicts with replay design')
    from converter_dynamics import parameters_from_inventory
    input_context=capture_context(design,{'retune':retune},operation='transport')
    endpoints=captured_endpoint_configurations(design,retune)
    environments=None if endpoints is None else captured_endpoint_environments(design,endpoints,retune)
    rows=[];conversion_s=sum(parameters_from_inventory(design.architecture).bit_durations_s)
    for index,stage in enumerate(retune['converter_stages']):
        if endpoints is not None:
            if stage['stage'] not in ('before','after'):
                raise ValueError('Configured converter stage must name its endpoint')
            index=0 if stage['stage']=='before' else 1
            endpoint=endpoints[index]
            if endpoint.engine!='rf' or endpoint.direction!='rx':
                raise ValueError('Converter replay requires an RF RX endpoint')
            env=environments[index]
        else:
            if index>=2:raise ValueError('Finite word fixture supports at most two stages')
            env=handover_environment(design,'rf',(2.4e9,2.484e9)[index])
        origin=(0.,.4e-6)[index]
        cfg=env['resolved_configuration'];carrier=cfg['reference_hz']
        chip=BehavioralChip(selected_transport_assumptions(env))
        chip.configure_numeric(engine='rf',rf=dict(sample_hz=cfg['sample_hz'],
            sample_clock_source='external_lo',lo_hz=carrier,lo_divider=cfg['sample_divider'],
            rx_cutoff_hz=rx_cutoff_hz,tx_cutoff_hz=tx_cutoff_hz))
        chip.configure_transport('exclusive');chip.start()
        # Analog capture is a warm-state fixture; record the incompatible cold
        # readiness explicitly before replaying it against an already active chip.
        times=np.asarray(stage['sample_times_s'])+conversion_s-origin
        words=[(int(i)&4095)|((int(q)&4095)<<12) for i,q in stage['words']]
        seen=[]
        def event(index):return float(times[index]) if index<len(times) else None
        def source(index):seen.append(index);return words[index]
        horizon=float(np.nextafter(stage['final_state']['end_time_s']-origin,np.inf))
        args=dict(mode=1,source_hz=cfg['sample_hz'],sample_bits=24,frames=16,
            directions=('rx',),rx_event_time=event,rx_source=source,epoch=chip.epoch,until_s=horizon)
        try:chip.transfer(**args)
        except ValueError as error:
            assert 'Active current-epoch' in str(error)
        else:raise AssertionError('Unready capture accepted')
        readiness=chip.ready_at
        chip.advance(readiness)
        flow=chip.transfer(**args)
        assert flow['fault'] is None and seen==list(range(len(words)))
        delivered=list(chip.stream['rx_words'])
        actual=[(word>>bit)&1 for word in delivered for bit in range(10)]
        expected=[(word>>bit)&1 for word in words for bit in range(24)]
        assert actual==expected[:len(actual)]
        discarded=chip.stop()
        assert 24*len(words)==10*len(delivered)+discarded['rx_bits']
        rows.append(dict(design_provenance=design.provenance(),resolved_configuration=env['resolved_configuration'],
            scenario_overrides=env['scenario_overrides'],scenario_assumptions=env['scenario_assumptions'],filter_configuration=dict(rx_cutoff_hz=rx_cutoff_hz,tx_cutoff_hz=tx_cutoff_hz),stage=stage['stage'],observed_duration_s=horizon,
            startup_floor_s=readiness,unready_replay_rejected=True,
            d2h_word_hz=cfg['host_word_hz'],converter_words=len(words),flow=flow,
            delivered_words=len(delivered),discarded=discarded))
    return dict(design_provenance=design.provenance(),input_capture_context=input_context['input_capture_context'],input_capture_scope=('Design-bound capture' if capture_provenance is not None else 'Unbound word fixture; transport-only evidence'),stages=rows,scope='Finite real SAR words at conversion-completion times through selected-rate transport, starting a fresh D2H frame in each separately qualified warm replay. No invented tail samples or host drain beyond capture. Timestamp translation to an already active chip is a transport-only check, not an integrated retune lifecycle. Cold/unready replay is rejected; analog acquisition capture does not establish the configured readiness floor. Zero delivered words is not a successful payload demonstration.')


def replay_context(design, captures, rx_cutoff, tx_cutoff):
    return dict(capture_context(design,captures,operation='replay'),
        filter_configuration=dict(rx_cutoff_hz=rx_cutoff,tx_cutoff_hz=tx_cutoff))


def extended_sar_transport(contract,retune,*,qualification_trace=None,d2h_edges_s=None,filter_qualification=None,qualification_max_age_s=None,design=None,rx_cutoff=None,tx_cutoff=None):
    """One absolute RF-destination transition through rearm and real SAR delivery."""
    design=b.design_for_contract(contract,design)
    filters=lifecycle_filter_settings(design,rx_cutoff,tx_cutoff)
    rx_cutoff=filters['rx_cutoff_hz'];tx_cutoff=filters['tx_cutoff_hz']
    context=replay_context(design,{'retune':retune},rx_cutoff,tx_cutoff)
    endpoints=captured_endpoint_configurations(design,retune)
    environments=None if endpoints is None else captured_endpoint_environments(design,endpoints,retune)
    if environments is not None:
        destination=environments[1]
        context.update(resolved_configuration=destination['resolved_configuration'],
            scenario_overrides=destination['scenario_overrides'],
            scenario_assumptions=destination['scenario_assumptions'])
    if not retune['numerical_feedback_converged']:
        return dict(context,verdict='rejected_unconverged_analog_feedback',delivered_host_words=0)
    after=retune['converter_stages'][-1];carrier=retune['final_carrier_hz']
    supply_checks=[stage['supply_acceptance'] for stage in retune['converter_stages']]
    floor,ceiling=converter_supply_window(contract)
    acceptance=dict(kind='offline_model_supply_validity',minimum_required_v=floor,maximum_required_v=ceiling,
        passed=all(row['invalid_points']==0 and floor<=row['evaluated_interval_v'][0] and row['evaluated_interval_v'][1]<=ceiling for row in supply_checks),
        evaluated_interval_v=[min(row['evaluated_interval_v'][0] for row in supply_checks),max(row['evaluated_interval_v'][1] for row in supply_checks)],
        scope='All supply values actually used by SAR acquisition/idle/decision equations. Sampled validity screen; not a continuous minimum bound or an implemented hardware READY monitor.')
    if not acceptance['passed']:
        return dict(context,analog_acceptance=acceptance,delivered_host_words=0,
            verdict='rejected_supply_outside_model_domain',
            scope='Reject this whole lifecycle before promoting it to accepted transport evidence. Does not predict hardware fault latency; out-of-domain codes are not qualified outputs.')
    initial_engine='wire' if retune['direction']=='wired_to_rf' else 'rf'
    if endpoints is None:
        initial=handover_environment(design,initial_engine,2.5e9 if initial_engine=='wire' else 2.4e9)
        environment=handover_environment(design,'rf',carrier)
    else:
        if (endpoints[0].engine!=initial_engine or endpoints[1].engine!='rf'
                or endpoints[1].direction!='rx' or endpoints[1].reference_hz!=carrier):
            raise ValueError('Replay endpoints conflict with captured transition')
        initial,environment=environments
    context['resolved_configuration']=environment['resolved_configuration']
    chip=BehavioralChip(selected_transport_assumptions(environment))
    def configure(env):
        cfg=env['resolved_configuration']
        if cfg['engine']=='wire':
            chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=cfg['line_rate_bps']))
        else:
            chip.configure_numeric(engine='rf',rf=dict(sample_hz=cfg['sample_hz'],
                sample_clock_source='external_lo',lo_hz=cfg['reference_hz'],lo_divider=cfg['sample_divider'],
                rx_cutoff_hz=rx_cutoff,tx_cutoff_hz=tx_cutoff))
        chip.a=selected_transport_assumptions(env)
    configure(initial)
    chip.configure_transport('exclusive')
    qualification_report=None
    if qualification_trace is not None:
        events,qualification_report=converter_qualification_events(contract,qualification_trace,max_observation_age_s=qualification_max_age_s,design=design)
        if filter_qualification is not None:
            valid_at=filter_qualification['valid_at_s']
            old_times=np.asarray([t for t,v in events]);old_valid=[v for t,v in events]
            times=sorted(set(old_times.tolist()+[valid_at]))
            events=[(float(t),bool(old_valid[np.searchsorted(old_times,t,side='right')-1] and t>=valid_at)) for t in times]
            qualification_report['filter_history']=filter_qualification
            qualification_report['combined_transitions']=events
        chip.attach_analog_qualification(events)
    elif filter_qualification is not None:
        raise ValueError('Filter qualification must join the converter validity observations')
    monitor=np.r_[retune['pre_transition_monitor_times_s'],after['sample_times_s']]
    chip.attach_reference(monitor,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
    chip.start();chip.advance(.2e-6)
    assert chip.state=='acquiring'
    first_epoch=chip.epoch;first_discard=chip.stop()
    configure(environment)
    chip.advance(.4e-6);chip.start()
    armed_at=chip.time
    # Observe the real precomputed validity timeline before selecting a deadline.
    chip.advance(armed_at+1e-9)
    ready_at=chip.ready_at
    if not np.isfinite(ready_at) and filter_qualification is not None:
        assert chip.state=='acquiring'
        chip.advance(filter_qualification['valid_at_s'])
        ready_at=chip.ready_at
    if not np.isfinite(ready_at):raise ValueError('Analog qualification has no finite startup deadline')
    # Converters ran through qualification on the same retained state. Only
    # apertures at/after READY are eligible for this new stream epoch.
    samples=np.asarray(after['sample_times_s']);eligible=samples>=ready_at
    times=samples[eligible]+sum(b.environment_converter_parameters(environment).bit_durations_s)
    words=[(int(i)&4095)|((int(q)&4095)<<12) for i,q in np.asarray(after['words'])[eligible]]
    horizon=float(np.nextafter(after['final_state']['end_time_s'],np.inf))
    seen=[]
    def source(index):seen.append(index);return words[index]
    event=lambda index:float(times[index]-ready_at) if index<len(times) else None
    args=dict(mode=1,source_hz=environment['resolved_configuration']['sample_hz'],sample_bits=24,frames=max(16,len(words)),
        directions=('rx',),rx_source=source,rx_event_time=event,epoch=chip.epoch,
        depth_bits=contract['transport']['scheduling']['ingress_bits_per_source'])
    host=None
    if d2h_edges_s is not None:
        host_edges=np.asarray(d2h_edges_s);host_edges=host_edges[host_edges>=ready_at]
        host=lambda index:float(host_edges[index]-ready_at) if index<len(host_edges) else None
        args['d2h_event_time']=host
    try:chip.transfer(**args,until_s=horizon-ready_at)
    except ValueError as error:assert 'Active current-epoch' in str(error)
    else:raise AssertionError('Unready converter payload accepted')
    chip.advance(ready_at);assert chip.state=='active'
    source=chip.bind_stream_callback(source);event=chip.bind_stream_callback(event)
    args.update(rx_source=source,rx_event_time=event)
    if host is not None:
        host=chip.bind_stream_callback(host);args['d2h_event_time']=host
    for end in (ready_at+.37e-6,ready_at+.9e-6,horizon):
        flow=chip.transfer(**args,until_s=end-ready_at)
        assert flow['fault'] is None
    delivered=list(chip.stream['rx_words'])
    actual=[(word>>bit)&1 for word in delivered for bit in range(10)]
    expected=[(word>>bit)&1 for word in words for bit in range(24)]
    assert actual and actual==expected[:len(actual)]
    assert seen==list(range(len(words)))
    final_epoch=chip.epoch;discarded=chip.stop()
    assert 24*len(words)==len(actual)+discarded['rx_bits']
    for callback in ((source,event,host) if host is not None else (source,event)):
        try:callback(0)
        except ValueError:pass
        else:raise AssertionError('Stopped converter callback accepted')
    return dict(context,analog_acceptance=acceptance,analog_qualification=qualification_report,armed_at_s=armed_at,ready_at_s=ready_at,observed_until_s=horizon,
        first_epoch=first_epoch,stream_epoch=final_epoch,first_discard=first_discard,
        pre_ready_converter_samples=int(np.count_nonzero(~eligible)),eligible_converter_samples=len(words),
        delivered_host_words=len(delivered),delivered_prefix_correct=True,flow=flow,discarded=discarded,
        unready_payload_rejected=True,stale_callbacks_rejected=True,
        direction=retune['direction'],scope='Absolute analog/model time preserved through arm, interrupted acquisition at 0.2 us, rearm at 0.4 us, configured startup timer plus divided-reference presence, and actual SAR delivery. Powered package, initially discharged SAR with reference bias enabled at t=0, and prescribed transition guards. No ADC apertures in wired mode. Divided reference samples share converter timing; only selected rising crossings are searched on the analytic tail, not every LO edge. When supplied, D2H edges must share the configured converter phase; otherwise host timing remains uniform. The finite RX queue uses the contract depth. Reference recharge is iteratively coupled, other switching remains prescribed. Optional model-observed reference/supply validity is reported separately; no physical READY sensing/noise qualification, full supply startup, mid-conversion cancellation, protocol payload or later fault-recovery proof.')


def converter_qualification_events(contract,trace,*,max_observation_age_s=None,design=None):
    """Ideal model observations of reference charge and evaluated supply."""
    validate_contract_provenance(contract,trace.get('design_provenance'))
    if design is not None:
        design=b.design_for_contract(contract,design)
        context=continuation_context(design,{'qualification_trace':trace})
    else:
        context=dict(source_design_provenance=trace.get('design_provenance'),
            input_capture_scope='design_bound' if trace.get('design_provenance') is not None else 'unbound_numerical_fixture')
    if max_observation_age_s is not None and (not np.isfinite(max_observation_age_s) or max_observation_age_s<=0):
        raise ValueError('Positive finite converter observation age required')
    spec=contract['physical_services']['sar_timing']['startup']
    low,high=spec['model_reference_window_v'];floor,ceiling=converter_supply_window(contract)
    segments=trace['segments'];cap=trace['reference_cap_f']
    times=np.r_[segments[:,0],segments[:,0]+segments[:,1]]
    values=np.r_[segments[:,2],segments[:,2]+segments[:,5]/cap]
    # Bias validity is observed in quiet recovery, at acquisition, and where
    # the modeled comparator actually consumes the reference. Charge-step
    # excursions remain in the converter error/charge reports, not erased.
    windows=np.asarray(trace['conversion_windows_s'])
    selected=np.searchsorted(windows[:,0],times,side='right')-1
    switching=(selected>=0)&(times<=windows[np.maximum(selected,0),1])
    decisions=np.asarray(trace['decision_reference_observations'])
    times=np.r_[times[~switching],windows[:,0],decisions[:,0]]
    values=np.r_[values[~switching],trace['acquisition_reference_v'],decisions[:,1]]
    order=np.argsort(times,kind='stable');times=times[order];values=values[order]
    rt,index=np.unique(times,return_index=True)
    # At a coincident pre/post-charge observation, invalid wins conservatively.
    rv=np.logical_and.reduceat((values>=low)&(values<=high),index)
    observations=trace['supply_observations'];order=np.argsort(observations[:,0],kind='stable')
    st,ix=np.unique(observations[order,0],return_index=True)
    sv=np.logical_and.reduceat((observations[order,1]>=floor)&(observations[order,1]<=ceiling),ix)
    expiry=[] if max_observation_age_s is None else np.nextafter(np.r_[rt,st]+max_observation_age_s,np.inf)
    timeline=np.unique(np.r_[0.,rt,st,expiry]);ri=np.searchsorted(rt,timeline,side='right')-1;si=np.searchsorted(st,timeline,side='right')-1
    valid=(ri>=0)&(si>=0)&rv[np.maximum(ri,0)]&sv[np.maximum(si,0)]
    if max_observation_age_s is not None:
        # Fresh supply readings cannot refresh stale reference observations,
        # or vice versa. Expiry events are watchdog evaluations, not readings.
        valid &= ((timeline-rt[np.maximum(ri,0)])<=max_observation_age_s)
        valid &= ((timeline-st[np.maximum(si,0)])<=max_observation_age_s)
    changes=np.r_[True,valid[1:]!=valid[:-1]]
    events=[(float(t),bool(v)) for t,v in zip(timeline[changes],valid[changes])]
    return events,dict(context,reference_window_v=[low,high],minimum_supply_v=floor,maximum_supply_v=ceiling,
        max_observation_age_s=max_observation_age_s,
        final_reference_observation_s=float(rt[-1]),final_supply_observation_s=float(st[-1]),
        transitions=events,observation_count=len(np.unique(np.r_[rt,st])),watchdog_evaluation_count=len(timeline),
        scope='Ideal zero-latency observations of quiet reference recovery endpoints, acquisition and comparator-decision reference values, plus the supply values used by converter equations. In-conversion charge-step excursions remain in the conversion accuracy and charge reports rather than being classified as bias loss. Reference recovery is monotone within each held segment. Optional age bounds expire reference and supply coverage independently; expiry events do not assert new measurements. Without an age bound, held validity is a legacy control. Supply extrema between evaluated points, sensing accuracy, independent threshold source and hardware monitor latency remain unqualified. This coarse bias window does not establish ADC ENOB or RF quality.')


def fault_recovery_transport(contract,retune,recovery,capture,fault,*,design=None,rx_cutoff=None,tx_cutoff=None):
    """Actual retained SAR words and divided host clocks across two epochs."""
    design=b.design_for_contract(contract,design)
    filters=lifecycle_filter_settings(design,rx_cutoff,tx_cutoff)
    rx_cutoff=filters['rx_cutoff_hz'];tx_cutoff=filters['tx_cutoff_hz']
    context=replay_context(design,dict(retune=retune,recovery=recovery,capture=capture,fault=fault),rx_cutoff,tx_cutoff)
    endpoints=captured_endpoint_configurations(design,retune)
    environments=None if endpoints is None else captured_endpoint_environments(design,endpoints,retune)
    if environments is not None:
        destination=environments[1]
        context.update(resolved_configuration=destination['resolved_configuration'],
            scenario_overrides=destination['scenario_overrides'],
            scenario_assumptions=destination['scenario_assumptions'])
    before,after=retune['converter_stages']
    floor,ceiling=converter_supply_window(contract)
    supply_min=min(stage['converter']['evaluated_supply_interval_v'][0] for stage in (before,after))
    supply_min=min(supply_min,recovery['converter']['evaluated_supply_interval_v'][0])
    supply_max=max(stage['converter']['evaluated_supply_interval_v'][1] for stage in (before,after))
    supply_max=max(supply_max,recovery['converter']['evaluated_supply_interval_v'][1])
    if not recovery['numerical_feedback_converged'] or supply_min<floor or supply_max>ceiling:
        return dict(context,verdict='rejected_analog_trajectory',numerical_feedback_converged=recovery['numerical_feedback_converged'],minimum_evaluated_supply_v=supply_min,maximum_evaluated_supply_v=supply_max)
    carrier=retune['final_carrier_hz']
    if endpoints is None:
        initial=handover_environment(design,'rf',2.4e9)
        environment=handover_environment(design,'rf',carrier)
    else:
        if any(c.engine!='rf' or c.direction!='rx' for c in endpoints) or endpoints[1].reference_hz!=carrier:
            raise ValueError('Recovery requires matching RF RX endpoints')
        initial,environment=environments
    context['resolved_configuration']=environment['resolved_configuration']
    chip=BehavioralChip(selected_transport_assumptions(initial))
    def configure(env):
        cfg=env['resolved_configuration']
        chip.configure_numeric(engine='rf',rf=dict(sample_hz=cfg['sample_hz'],sample_clock_source='external_lo',
            lo_hz=cfg['reference_hz'],lo_divider=cfg['sample_divider'],rx_cutoff_hz=rx_cutoff,tx_cutoff_hz=tx_cutoff))
    configure(initial);chip.configure_transport('exclusive')
    qualification_events,qualification_report=converter_qualification_events(contract,capture['trace'],design=design)
    chip.attach_analog_qualification(qualification_events)
    all_samples=np.r_[after['sample_times_s'],recovery['sample_times_s']]
    all_words=np.vstack((after['words'],recovery['words']))
    all_completion=all_samples+contract['physical_services']['sar_timing']['maximum_conversion_s']
    monitor=np.r_[before['sample_times_s'],all_samples]
    chip.attach_reference(monitor,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
    chip.start();chip.advance(.2e-6);chip.stop();configure(environment);chip.a=selected_transport_assumptions(environment)
    chip.advance(.4e-6);chip.start();chip.advance(chip.ready_at)
    assert chip.state=='active'
    rows=[];callbacks=[]
    def stream(until):
        origin=chip.time;epoch=chip.epoch
        selected=all_samples>=origin
        times=all_completion[selected]
        words=[(int(i)&4095)|((int(q)&4095)<<12) for i,q in all_words[selected]]
        edges=capture['d2h_edges_s'];edges=edges[edges>=origin]
        seen=[]
        def source(index):seen.append(index);return words[index]
        source=chip.bind_stream_callback(source)
        event=chip.bind_stream_callback(lambda index:float(times[index]-origin) if index<len(times) else None)
        host=chip.bind_stream_callback(lambda index:float(edges[index]-origin) if index<len(edges) else None)
        callbacks.extend((source,event,host))
        flow=chip.transfer(mode=1,source_hz=environment['resolved_configuration']['sample_hz'],sample_bits=24,frames=256,
            depth_bits=contract['transport']['scheduling']['ingress_bits_per_source'],directions=('rx',),
            epoch=epoch,rx_source=source,rx_event_time=event,d2h_event_time=host,until_s=until-origin)
        delivered=list(chip.stream['rx_words'])
        actual=[(word>>bit)&1 for word in delivered for bit in range(10)]
        expected=[(words[index]>>bit)&1 for index in seen for bit in range(24)]
        assert actual and actual==expected[:len(actual)]
        stopped_at=chip.time;discarded=chip.stop()
        assert len(expected)==len(actual)+discarded['rx_bits']
        stale=0
        for callback in (source,event,host):
            try:callback(0)
            except ValueError:stale+=1
            else:raise AssertionError('Stopped analog payload callback accepted')
        row=dict(epoch=epoch,ready_at_s=origin,stopped_at_s=stopped_at,flow=flow,
            delivered_host_words=len(delivered),converter_words_consumed=len(seen),discarded=discarded,
            prefix_correct=True,all_bits_accounted=True,stale_callbacks_rejected=stale)
        rows.append(row);return row
    lost=stream(fault['restart_at_s'])
    assert lost['flow']['fault']=='reference_lost'
    assert fault['loss_at_s']<lost['stopped_at_s']<fault['restart_at_s']
    chip.advance(fault['restart_at_s']+100e-9);chip.start();rearm=chip.time;ready=chip.ready_at
    chip.advance(ready);assert chip.state=='active'
    recovered=stream(float(recovery['final_state']['end_time_s']))
    assert recovered['flow']['fault'] is None and recovered['epoch']!=lost['epoch']
    edges=capture['d2h_edges_s']
    quiet=(edges>fault['loss_at_s']+100e-9)&(edges<fault['restart_at_s']-100e-9)
    assert not np.any(quiet)
    return dict(context,analog_qualification=qualification_report,verdict='conditional_coupled_analog_replay',stages=rows,rearmed_at_s=rearm,recovered_ready_at_s=ready,
        missing_interval_host_edges=int(np.count_nonzero(quiet)),minimum_evaluated_supply_v=supply_min,
        samples_excluded_during_recovery=int(np.count_nonzero((all_samples>=lost['stopped_at_s'])&(all_samples<ready))),
        scope='One warm retune/fault/rearm stream consumes retained SAR words and common /16 host, /64 sample clock phase. Independent reference monitor detects actual missing clocks; STOP discards the bounded queue and invalidates epoch callbacks. Converters and prescribed clock/load activity continue while payload is unready; no analog reset or power-saving STOP is modeled. Readiness requires the configured startup guard, reference-clock presence and model-observed analog validity; loss of the latter faults payload. Offline full-trajectory supply/convergence screening also remains. The analog validity observer is ideal and does not qualify physical sensing. Guarded FFT replay, known tone and assumed GPIO capture; not online analog READY, packet interoperability or physical host-pattern power closure.')


def filter_startup_screen(contract):
    """Configuration-dependent memory bound and an independently solved witness."""
    from scipy import signal,linalg
    from selected_rf import filter_settling_requirement
    cutoffs=sorted({float(row['rf']['rx_cutoff_hz']) for row in contract['behavioral_configuration_cases'] if row['engine']=='rf'})
    guard=contract['physical_services']['sar_timing']['startup']['assigned_guard_s']
    rows=[]
    # Real companion-state model, independent of the modal-residue bound.
    A,B,C,D=signal.tf2ss(*signal.ellip(5,1,36.40776933523119,1,analog=True))
    x=np.linalg.solve(1j*np.eye(len(A))-A,B[:,0])
    for cutoff in cutoffs:
        row=filter_settling_requirement(family='rx_finite_zero',cutoff_hz=cutoff)
        weights=np.asarray(row['modal_weights']);decay=np.asarray(row['decay_per_s'])
        witness=complex((C@linalg.expm(A*2*np.pi*cutoff*guard)@x).item())
        row.update(guard_s=guard,old_history_bound_at_guard=float(sum(weights*np.exp(-decay*guard))),
            sinusoidal_history_witness_at_guard=abs(witness),
            witness_phase_rad=float(-np.angle(witness)),
            guard_sufficient=row['settling_s']<=guard,
            counterexample_exceeds_budget=abs(witness)>row['error_budget'])
        rows.append(row)
    return dict(cases=rows,error_budget_scope='Assigned 1/1024 normalized output-error allocation with unit bounded input history at the same fixed gain; not a protocol EVM or ADC ENOB guarantee.',
        witness='Unit real sinusoid at cutoff in steady state before t=0, then zero input. Choose the reported phase to maximize its real output at the 20 us guard. Independent real companion-state exponential; no fitted or synthetic pole.',
        decision='Preserve generic cutoff selection; require configuration-dependent settling before admission when old filter state is unqualified. Retained bias alone is insufficient after a disturbance. External preselection and uninterrupted settled operation can reduce the history bound; neither is assumed automatically.',
        scope='Selected ideal linear finite-zero response. Bound applies for all time after the reported deadline and all bounded prior input histories under fixed coefficients. It does not bound arbitrary initial capacitor charge, nonlinear/internal saturation, changed-filter state mapping, bias/reference startup, noise or blocker rejection during new forcing.')


def reference_startup_screen(contract,*,design=None):
    """Counterexample to timer-only READY using the same reference recurrence."""
    from converter_dynamics import paired_sar,discharged_sar_state,parameters_from_inventory
    design=b.design_for_contract(contract,design)
    nominal=design.architecture['blocks']['refbuf']['parameters']['source_limit_a']
    ready=contract['physical_services']['sar_timing']['startup']['assigned_guard_s']
    config=design.configure(engine='rf',direction='rx',reference_hz=2.484e9,sample_divider=64,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    samples=ready+np.arange(16)/config.sample_hz;values=np.full(16,.3+.2j)
    rows=[]
    for current,age in ((nominal,ready),(nominal,50e-9),(nominal,200e-9),(nominal/4,200e-9),(nominal/4,ready)):
        variant=(design if current==nominal else design.hypothetical(
            reason='Quarter-current reference startup sensitivity',
            changes={'blocks.refbuf.parameters.source_limit_a':current}))
        resolved=variant.configure(engine='rf',direction='rx',reference_hz=config.reference_hz,
            sample_divider=config.sample_divider,pga_gain_db=config.pga_gain_db)
        p=parameters_from_inventory(variant.architecture)
        words,report,trace=paired_sar(values,values,samples,lambda q:np.ones_like(q),
            lambda q:np.full_like(q,3.),parameters=p,noise=False,idle_step_s=1e-9,
            initial_state=discharged_sar_state(parameters=p,at_s=ready-age))
        assert abs(report['reference_charge_balance_residual_c'])<1e-20
        rows.append(dict(design_provenance=variant.provenance(),resolved_configuration=resolved.record(),
            scenario_overrides=[],probe_assumptions=dict(rail_v=3.,reference_target_v=1.,
                constant_input_iq_v=[.3,.2],noise=False,initial_reference_state='discharged'),
            reference_limit_a=current,bias_age_at_nominal_ready_s=age,
            first_acquisition_reference_v=report['first_acquisition_reference_v'],
            first_transport_word=words[0].tolist(),last_transport_word=words[-1].tolist(),
            maximum_native_code_error_lsb=report['maximum_code_error_lsb']))
    assert rows[0]['maximum_native_code_error_lsb']<=2 and rows[-1]['maximum_native_code_error_lsb']<=2
    assert rows[1]['maximum_native_code_error_lsb']>50 and rows[3]['maximum_native_code_error_lsb']>50
    return dict(design_provenance=design.provenance(),assigned_guard_s=ready,cases=rows,timer_and_reference_clock_alone_insufficient=True,
        requirement_owner='spec/contract.json:physical_services.sar_timing.startup',
        scope='Same current-limited reference and SAR equations, discharged charge state, already-valid 3 V rail, fixed 1 V reference target, known constant input and no noise. Quarter-current row is a sensitivity case, not an inferred GF180 bound. Demonstrates dependence on actual bias-enable time and available recharge; 200 ns is not a universal startup requirement. Does not implement an analog READY monitor or full rail/bias power-up.')


def retained_sar_refinement(contract,*,design=None):
    design=b.design_for_contract(contract,design)
    capture={};package=full_package_handover(contract,adc_current_a=None,rf_retune=True,capture=capture,design=design)
    coarse=retained_sar_retune(contract,feedback_grid_s=.125e-9,package_capture=(package,capture),design=design)
    fine=retained_sar_retune(contract,feedback_grid_s=.0625e-9,package_capture=(package,capture),design=design)
    comparisons=[]
    for a,z in zip(coarse['converter_stages'],fine['converter_stages']):
        same_count=a['samples']==z['samples']
        comparisons.append(dict(stage=a['stage'],same_sample_count=same_count,
            same_words=a['words']==z['words'],
            maximum_sample_time_difference_s=float(max(abs(np.asarray(a['sample_times_s'])-z['sample_times_s']))) if same_count else None,
            reference_state_difference_v=abs(a['final_state']['reference_v']-z['final_state']['reference_v'])))
    extended_capture={}
    extended=retained_sar_retune(contract,package_capture=(package,capture),extend_until_s=22e-6,capture_out=extended_capture,design=design)
    extended['transport']=extended_sar_transport(contract,extended,d2h_edges_s=extended_capture['d2h_edges_s'],design=design)
    extended_fine_capture={}
    extended_fine=retained_sar_retune(contract,feedback_grid_s=.0625e-9,package_capture=(package,capture),extend_until_s=22e-6,capture_out=extended_fine_capture,design=design)
    extended['feedback_grid_refinement']=dict(fine_grid_s=.0625e-9,
        fine_converged=extended_fine['numerical_feedback_converged'],
        stages=[dict(stage=a['stage'],same_words=a['words']==z['words'],
            maximum_sample_time_difference_s=float(np.max(abs(np.asarray(a['sample_times_s'])-z['sample_times_s']))),
            maximum_transport_code_difference=int(np.max(abs(np.asarray(a['words'])-z['words']))))
            for a,z in zip(extended['converter_stages'],extended_fine['converter_stages'])],
        fine_transport=extended_sar_transport(contract,extended_fine,d2h_edges_s=extended_fine_capture['d2h_edges_s'],design=design),
        scope='Recharge feedback grid only; same analog continuation and divided-clock root brackets. Does not bound physical timing/noise or unexamined LO edges.')
    low_supply=retained_sar_retune(contract,package_capture=(package,capture),extend_until_s=22e-6,supply_offset_v=-.3,design=design)
    extended['supply_rejection_control']=dict(offset_v=-.3,
        numerical_feedback_converged=low_supply['numerical_feedback_converged'],
        transport=extended_sar_transport(contract,low_supply,design=design),
        scope='Same forced package waveform and converter equations with a -300 mV local DC perturbation and assigned reference/delay sensitivities. Tests invalid-domain rejection, not a new feasible supply operating point.')
    assert extended['supply_rejection_control']['transport']['verdict']=='rejected_supply_outside_model_domain'
    extended.pop('package')
    coarse['extended_lifecycle']=extended
    fault_capture={}
    loss_at=extended['converter_stages'][-1]['final_state']['end_time_s']+2e-9
    coarse['clock_loss_package']=package_clock_loss(contract,capture,loss_at_s=loss_at,capture_out=fault_capture,design=design)
    extended['clock_loss_converter_continuation']=clock_loss_sar_continuation(contract,capture,fault_capture,extended,extended_capture,design=design)
    fault_result=extended['clock_loss_converter_continuation']
    fault_result['clock_grid_qualified']=coarse['clock_loss_package']['grid_clock_classification_agrees'] and len(set(fault_result['feedback_iterations'][-1]['raw_edge_counts_by_grid']))==1
    refined_fault=clock_loss_sar_continuation(contract,capture,fault_capture,extended_fine,extended_fine_capture,design=design)
    fault_result['feedback_grid_refinement']=dict(fine=refined_fault,
        same_words=fault_result['words']==refined_fault['words'],
        maximum_sample_time_difference_s=(float(np.max(abs(np.asarray(fault_result['sample_times_s'])-refined_fault['sample_times_s']))) if fault_result['samples']==refined_fault['samples'] else None),
        scope='Each recharge grid retains its own converged pre-fault converter state and full recharge history; same analytic base package and loss phase. Prefix validity is checked independently, not waived by matching words.')
    recovery_capture={}
    recovery=clock_loss_sar_continuation(contract,capture,fault_capture,extended_fine,extended_fine_capture,
        extend_until_s=45e-6,capture_out=recovery_capture,design=design)
    extended['clock_loss_recovery']=recovery
    recovery['transport']=fault_recovery_transport(contract,extended_fine,recovery,recovery_capture,fault_capture,design=design)
    fine.pop('package')  # Same full-network trajectory; retain it once in coarse.
    return coarse,dict(fine=fine,comparisons=comparisons,
        both_meet_feedback_stopping_criteria=coarse['numerical_feedback_converged'] and fine['numerical_feedback_converged'],
        scope='125/62.5 ps recharge-grid comparison on the identical 6.25 ps package trajectory, deterministic noise and input tone. Refines only the FFT feedback grid; idle forcing step, package grid, physical assumptions and uncertainty coverage remain separate.')


def selected_direction_control_audit(contract,*,design=None):
    """Expose whether the current runtime can execute the budgeted operation."""
    design=b.design_for_contract(contract,design)
    architecture=design.architecture
    rx_config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,sample_divider=64,
        pga_gain_db=max(architecture['blocks']['pga_i']['parameters']['gain_db']))
    tx_config=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64)
    environment=b.configured_environment(rx_config)
    if contract['transport']['word_bits']!=10 or any(
            architecture['blocks'][name]['parameters']['transport_bits']!=12 for name in ('adc_i','adc_q')):
        raise ValueError('Direction audit adapter requires 10-bit host and paired 12-bit samples')
    settings=dict(sample_hz=rx_config.sample_hz,sample_clock_source='external_lo',
        lo_hz=rx_config.reference_hz,lo_divider=rx_config.sample_divider,
        **lifecycle_filter_settings(design))
    def make_chip():
        return BehavioralChip(selected_transport_assumptions(environment))
    chip=make_chip();chip.configure_numeric(engine='rf',rf=settings)
    chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
    epoch=chip.epoch
    common=dict(mode=1,source_hz=rx_config.sample_hz,sample_bits=24,frames=2,epoch=epoch,
        depth_bits=contract['transport']['scheduling']['ingress_bits_per_source'])
    flow=chip.transfer(**common,directions=('rx',),rx_source=chip.bind_stream_callback(lambda i:i))
    assert flow['fault'] is None and chip.state=='active'
    before=chip.time
    try:
        chip.transfer(**common,directions=('tx',),tx_source=chip.bind_stream_callback(lambda i:0))
    except ValueError as error:
        rejection=str(error)
    else:rejection=None
    changed_time=chip.time!=before;changed_epoch=chip.epoch!=epoch
    discarded=chip.stop();chip.start()
    gated=make_chip();gated.configure_numeric(engine='rf',rf=settings)
    gated.configure_transport('exclusive');gated.start();gated.advance(gated.ready_at)
    origin=gated.time;gated.enable_rf_direction_gate(rx_completion_latency_s=contract['physical_services']['sar_timing']['maximum_conversion_s'])
    action=gated.schedule_rf_direction('tx',at_s=origin+1e-6,settle_s=contract['physical_services']['rf_settling_exploratory_targets_us']['same_channel_direction']*1e-6)
    emitted=[];received=[]
    def source(i):received.append(i);return i
    def host(i):return (i*73+19)&1023
    result=gated.transfer(mode=1,source_hz=rx_config.sample_hz,sample_bits=24,frames=40,depth_bits=contract['transport']['scheduling']['ingress_bits_per_source'],
        epoch=gated.epoch,directions=('rx','tx'),tx_prefill_bits=0,rx_source=source,tx_source=host,
        tx_host_enable=lambda time,index:index<64 or time>=action['ready_at_s'],
        tx_word_observer=lambda time,word:emitted.append((time,word)))
    assert result['fault'] is None and emitted and received and gated.epoch==action['epoch']
    actual=[(word>>bit)&1 for _,word in emitted for bit in range(24)]
    expected=[(host(i)>>bit)&1 for i in range(1000) for bit in range(10)]
    assert actual==expected[:len(actual)]
    assert min(time for time,_ in emitted)>=action['ready_at_s']
    return dict(design_provenance=design.provenance(),
        resolved_configurations=dict(rx=rx_config.record(),tx=tx_config.record()),scenario_overrides=[],
        selected_controls=settings,model_assumptions=dict(
            payload='Synthetic deterministic sample words; no analog waveform',
            direction_request_offset_s=1e-6,early_host_words=64),
        generic_gate=dict(action=action,epoch_preserved=True,actual_host_prefill=True,
        verified_tx_bits=len(actual),rx_completed_samples=len(received),first_tx_event_s=emitted[0][0],
        flow_fault=result['fault'],scope='Selected host rates and finite queues; retained epoch and sample/frame phase. Synthetic payload only; no retained analog integration or physical air-launch proof.'),direct_rx_to_tx_rejection=rejection,
        rejection_changed_time=changed_time,rejection_changed_epoch=changed_epoch,
        fallback_stop_discards=discarded,fallback_new_epoch=chip.epoch,
        fallback_startup_wait_s=chip.ready_at-chip.time,
        retained_clock_direction_operation_demonstrated='control_path_only',
        scope='Runtime control-surface audit only. Existing transfer direction is part of immutable stream geometry; STOP/rearm is a different operation. No analog waveform or packet deadline is qualified, and rejecting the requested operation is evidence of a gap, not a passed capability.')


def selected_turnaround_requirement(contract,*,design=None):
    """Inverse end-to-end response budget, with no invented FPGA execution time."""
    from check_contract import periodic_stream_bound
    from resource_configuration import rf_transition_budget
    design=b.design_for_contract(contract,design)
    config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,sample_divider=64,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    tx_config=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64)
    env=b.configured_environment(config)
    down_hz=env['host_spectrum']['d2h_word_hz'];up_hz=env['host_spectrum']['h2d_word_hz']
    fs=config.sample_hz;control_hz=config.control_hz;t=contract['transport']
    def service(rate):
        return periodic_stream_bound(arrival_item_hz=fs*(1+t['source_fast_ppm']/1e6),
            item_bits=24,word_hz=rate*(1-t['host_slow_ppm']/1e6),
            frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
            staging_frames=1,cdc_words=2)
    down=service(down_hz);up=service(up_hz);prefill=512
    settings=dict(sample_hz=fs,sample_clock_source='external_lo',lo_hz=2.4e9,
        lo_divider=64,**lifecycle_filter_settings(design))
    transition=rf_transition_budget(before=settings,after=settings,operation='turnaround',
        epoch=7,host_word_hz=up_hz,command_words=8,cdc_cycles=2,control_hz=control_hz,
        boundary_wait_s=64/down_hz,analog_settle_s=contract['physical_services']['rf_settling_exploratory_targets_us']['same_channel_direction']*1e-6,
        source_lock_s=0.,host_training_words=0,fpga_recovery_s=0.,deadline_s=10e-6)
    components=dict(last_conversion_s=contract['physical_services']['sar_timing']['maximum_conversion_s'],receive_transport_s=down['delay_bound_s'],
        rx_resampler_lookahead_s=32/fs,wait_command_frame_s=64/up_hz,
        command_boundary_analog_s=transition['total_s'],
        tx_interpolator_lookahead_s=32/20e6,
        tx_prefill_service_s=up['service_latency_s']+prefill/up['guaranteed_service_bps'])
    storage=t['scheduling']['ingress_bits_per_source']
    fits=bool(down['rate_stable'] and up['rate_stable'] and down['backlog_bound_bits']<=storage
        and prefill+up['backlog_bound_bits']<=storage and prefill>=up['backlog_bound_bits'])
    total=sum(components.values())
    return dict(design_provenance=design.provenance(),
        resolved_configurations=dict(rx=config.record(),tx=tx_config.record()),scenario_overrides=[],
        filter_configuration=lifecycle_filter_settings(design),
        model_assumptions=dict(rx_resampler_lookahead_samples=32,tx_interpolator_lookahead_samples=32,
            tx_interpolator_input_hz=20e6,tx_prefill_bits=prefill,
            scope='Explicit FPGA lookahead/prefill schedule; converter completion bound belongs to the shared contract'),
        components=components,assigned_overhead_s=total,
        diagnostic_windows=[dict(window_s=d,remaining_fpga_and_unmodeled_analog_s=d-total,
            nonnegative_residual=d>=total) for d in (10e-6,150e-6,192e-6)],
        storage_fit=fits,storage_bits=storage,tx_prefill_bits=prefill,
        tx_prefill_plus_backlog_bits=prefill+up['backlog_bound_bits'],
        h2d_word_hz=up_hz,d2h_word_hz=down_hz,control_hz=control_hz,transition=transition,
        scope='Assigned sequential budget after last required RF input sample, not a packet exchange. Selected same-frame scheduler with ppm margins. FPGA decoding/CRC/decision/generation, RX filter decision latency, air timestamp calibration and TX filter/output launch delay must fit the residual; their time is not zero. Conservative TX interpolation lookahead may be avoided only with an actually prepared response. Same-channel clocks/epoch retained, not STOP/rearm. Physical analog settling and control execution remain unverified.')


def delivered_iq_words(host_words):
    """Reassemble only complete 24-bit I/Q samples from 10-bit host transfers.

    No padding, source-array substitution or hidden access to queued samples.
    A partial final sample remains unavailable to the FPGA signal observer.
    """
    pending=0;count=0;rows=[]
    for word in host_words:
        if not 0<=int(word)<1024:raise ValueError('Expected unsigned 10-bit host words')
        pending|=int(word)<<count;count+=10
        while count>=24:
            packed=pending&((1<<24)-1);pending>>=24;count-=24
            i=packed&4095;q=(packed>>12)&4095
            rows.append((i-4096 if i>=2048 else i,q-4096 if q>=2048 else q))
    return np.asarray(rows,dtype=np.int64).reshape(-1,2),count


def loaded_wired_recovery(contract, *, chip=None, rail_voltage=None, rail_delay=None, analog_observer=None,design=None):
    if (rail_voltage is None)!=(rail_delay is None):
        raise ValueError('Shared rail voltage and delay must be supplied together')
    if rail_voltage is not None and not (callable(rail_voltage) and callable(rail_delay)):
        raise ValueError('Shared rail voltage and delay must be callable trajectories')
    from behavioral import BehavioralChip
    from wired_envelope import physical_receiver
    from protocol_signals import pcie_gen1_compliance_bits
    bits = pcie_gen1_compliance_bits(5000)
    from baseline_envelope import selected_environment, P
    design=b.design_for_contract(contract,design)
    config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
    environment=b.configured_environment(config)
    from dataclasses import asdict
    assumptions=selected_transport_assumptions(environment)
    prior_assumptions=None if chip is None else asdict(chip.a)
    if chip is not None and chip.state!='reset':
        raise ValueError('Loaded wired recovery requires a stopped chip before applying shared transport assumptions')
    dc = environment['ledger']['local_payload_clock_core_rail_v']
    stress, _, disturbance = shared_supply_disturbance(contract['physical_services']['external_clock_input'], shared_stress=True, stress_ripple_peak_v=0.0096)
    impairment = dict(jitter_rms_s=0.0, jitter_hz=25000000.0, noise_rms_v=0.01, offset_v=0.02, rail_tones=[], delay_tones=[], rail_dc_v=dc, signal_scale=dc / b.wired_gain_reference(environment), rail_at_s=lambda t: dc + float(disturbance(t)), delay_at_s=lambda t: float(disturbance(t, delay=True)))
    receiver_parameters=b.wired_receiver_inventory(environment)
    # This is a loss/recovery fixture: exceed the configured holdover instead
    # of relying on a historical 400-UI gap that the current receiver tolerates.
    fault_gap_ui=receiver_parameters['holdover_ui']+64
    if 4000+fault_gap_ui>=len(bits):raise ValueError('Recovery fixture lacks post-fault traffic')
    bits[4000:4000+fault_gap_ui]=[0]*fault_gap_ui
    impairment.update(ctle_zero_s=receiver_parameters['ctle_zero_s'],
        ctle_pole_s=receiver_parameters['ctle_pole_s'],
        detector_noise_rms_s=receiver_parameters['detector_noise_rms_s'],
        holdover_ui=receiver_parameters['holdover_ui'],
        signal_scale=impairment['signal_scale']*receiver_parameters['ctle_dc_gain'])
    receiver_fixture=dict(phase=.35,ppm=100.,tau=100e-12,cap=receiver_parameters['pad_cap_f'])
    receiver = physical_receiver(bits,config.line_rate_bps,impairment=impairment,**receiver_fixture)
    if chip is None:chip = BehavioralChip(assumptions)
    else:chip.a=assumptions
    chip.configure_numeric(engine='wire', timing=dict(line_rate_bps=2500000000.0))
    chip.configure_transport('exclusive')
    def arm():
        if chip.analog_qualification is not None and analog_observer is None:
            raise ValueError('Attached analog qualification requires independent recovery observations')
        if analog_observer is not None:
            chip.analog_qualification.observe(chip.time,analog_observer(chip.time))
        chip.start();armed=chip.time
        while chip.state=='acquiring':
            next_time=min(chip.time+100e-9,chip.ready_at)
            chip.advance(next_time)
            if analog_observer is not None:
                chip.analog_qualification.observe(next_time,analog_observer(next_time))
            chip.advance(next_time)
            if chip.time-armed>100e-6:raise ValueError('Wired recovery analog qualification did not complete')
        if chip.state!='active':raise ValueError('Wired recovery failed to arm')
    arm()
    peer_origin = chip.time
    if rail_voltage is not None:
        impairment['rail_at_s']=lambda t:float(rail_voltage(peer_origin+t))
        impairment['delay_at_s']=lambda t:float(rail_delay(peer_origin+t))

    def transfer():
        offset = receiver.word_index
        stream_origin = chip.time
        accepted = []

        def forecast(i):
            index = offset + i
            if receiver.pending is None:
                due = receiver.forecast(index)
            else:
                assert index == receiver.word_index
                due = receiver.predicted[0].last_timestamp
            return peer_origin + due - stream_origin

        def valid(i):
            okay = all((v for _, v in receiver.predicted[1]))
            receiver.commit(offset + i)
            return bool(okay)

        def consume(i):
            okay = receiver.timing_qualified
            word = receiver.consume(offset + i)
            if okay:
                accepted.append(word)
            return word
        result = chip.transfer(mode=1, source_hz=250000000.0, sample_bits=10, frames=128, depth_bits=contract['transport']['scheduling']['ingress_bits_per_source'], directions=('rx',), epoch=chip.epoch, fault_on_rx_loss=True, rx_event_time=chip.bind_stream_callback(forecast), rx_valid=chip.bind_stream_callback(valid), rx_source=chip.bind_stream_callback(consume), analog_observer=None if analog_observer is None else chip.bind_stream_callback(analog_observer), analog_observation_period_s=100e-9)
        return (result, accepted)
    result, _ = transfer()
    assert result['fault'] == 'rx_qualification_lost', result
    old_epoch = chip.epoch
    fault_time = chip.time
    fault_index = receiver.word_index
    from recovery_mailbox import StickyFaultPublication, fault_notification_budget
    publication = StickyFaultPublication(1e-07)
    publication.capture(fault_time, old_epoch, result['fault'])
    assert publication.snapshot(fault_time) is None
    poll = peer_origin
    while poll < fault_time:
        poll += 1e-05
    while publication.snapshot(poll) is None:
        poll += 1e-05
    observed = publication.snapshot(poll)
    assert observed == (old_epoch, 'rx_qualification_lost')
    host_ready = poll + 32 / 25000000.0 + 1e-06
    budget = fault_notification_budget(line_rate_bps=2500000000.0, spi_hz=25000000.0, poll_start_interval_s=1e-05, detection_s=0.0, publication_s=1e-07, host_service_s=1e-06)
    assert host_ready - fault_time <= budget['notification_bound_s']
    chip.wait_faulted(host_ready)
    assert chip.state == 'fault'
    assert chip.epoch == old_epoch
    chip.stop()
    publication.acknowledge_stop(host_ready, stopped_epoch=old_epoch, new_epoch=chip.epoch)
    arm()
    assert chip.time - fault_time >= chip.a.startup_s - 1e-15
    rearmed_at = chip.time
    discarded = receiver.discard_through(chip.time - peer_origin)
    assert discarded > 4900
    assert receiver.word_index > fault_index + 4900
    result, accepted = transfer()
    assert result['fault'] is None
    assert chip.epoch > old_epoch
    words = chip.stream['rx_words']
    assert len(words) > 500
    assert words == accepted[:len(words)]
    assert receiver.timing_qualified
    return dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=[],stress=stress,local_dc_rail_v=dc,peer_duration_s=len(bits)/config.line_rate_bps,
        injected_transition_gap_ui=fault_gap_ui,
        model_role='shared_transport_with_explicit_loaded_receiver_fixture',
        transport_assumptions=asdict(assumptions),
        replaced_injected_assumptions=prior_assumptions,
        transport_basis=dict(encoding='exclusive_dense',
            ingress_bits=contract['transport']['scheduling']['ingress_bits_per_source'],
            egress_bits=contract['transport']['scheduling']['egress_bits_per_source'],
            allocation_status=contract['transport']['scheduling']['fifo_budget_status'],
            allocation_owner='contract.json:transport.scheduling',
            actual_rtl_capacity_qualified=False),
        receiver_fixture=dict(receiver_fixture,
            impedance_scope='Shared balanced pad and nominal CTLE; assigned remote switch pole, not extracted circuitry',
            phase_unit='UI',ppm_scope='remote peer frequency error',
            tau_unit='s',cap_unit='F',
            impairment={key:value for key,value in impairment.items() if not callable(value)},
            waveform_source='pcie_gen1_compliance_bits_with_forced_zero_run',
            reason='Isolate retained receiver state and host fault recovery under assigned analog loading'),
        rail_source='external_trajectory' if rail_voltage is not None else 'steady_wired_load',
        rail_trajectory_scope=('Caller-supplied voltage/delay pair; waveform provenance belongs to the calling bench'
            if rail_voltage is not None else 'Shared wired DC with explicitly assigned supply disturbance'),
        independent_analog_observations=analog_observer is not None,
        ingress_bits=contract['transport']['scheduling']['ingress_bits_per_source'],
        fault_time_s=fault_time,host_service_complete_s=host_ready,rearmed_at_s=rearmed_at,
        notification_budget=budget,discarded_receiver_words=discarded,
        fault_receiver_word=fault_index,old_epoch=old_epoch,new_epoch=chip.epoch,
        resumed_host_words=len(words),resumed_payload_matches_receiver=True,
        final_cdr_qualified=bool(receiver.timing_qualified),
        scope='Loaded CDR and generic host transport with continuous peer, sticky transaction-level fault observation and assigned polling/restart timing. Steady wired DC plus shared imposed ripple, not retained RF/wired load transitions. No physical loss-detector/CDC/SPI timing, serialized recovery-command execution, FPGA quarantine implementation, independent BER or protocol alignment proof.')


def shared_supply_disturbance(timing, *, shared_stress, stress_ripple_peak_v=.060, stress_ripple_hz=10e6):
    """Common imposed rail/timing envelope; not a package-derived bound."""
    stress=dict(source_offset_v=-.033 if shared_stress else 0.,
        ripple_peak_v=stress_ripple_peak_v if shared_stress else 0.,ripple_hz=stress_ripple_hz,
        delay_sensitivity_multiplier=4. if shared_stress else 1.,
        scope='Assigned simultaneous stress, not a package-derived bound: -1% source, rail disturbance at the recorded amplitude and frequency and fourfold delay sensitivity. One analytic disturbance drives converter/gain rails and filtered LO/sample/monitor timing. Does not cover host harmonics, oscillator phase noise, cold startup or uncertain rail ownership.')
    sensitivity=timing['supply_sensitivity_ps_per_mv']*1e-9*stress['delay_sensitivity_multiplier']
    def disturbance(times,*,delay=False):
        times=np.asarray(times,float);angle=2*np.pi*stress['ripple_hz']*times
        if delay:
            ratio=stress['ripple_hz']/timing['supply_delay_pole_hz']
            return sensitivity*(stress['source_offset_v']+stress['ripple_peak_v']/np.sqrt(1+ratio**2)*np.sin(angle-np.arctan(ratio)))
        return stress['source_offset_v']+stress['ripple_peak_v']*np.sin(angle)
    return stress,sensitivity,disturbance


def ownership_load_trace(contract,*,lo_divider=64,wideband=False,tx_fpga_preemphasis=None,shared_stress=False,turnaround=False,tx_nominal_gain=4.5,tx_native_peak=50.,packet_rx=False,stress_ripple_hz=10e6,stress_ripple_peak_v=.060,packet_request=False,packet_reply=False,wired_cdr=False,wired_encoded=False,wired_fail_closed=False,wired_noise_control="nominal",wired_equalized=False,wired_tx_electrical=False,wired_recovery=False,qualification_max_age_s=200e-9,independent_analog_observations=True,direct_usb=False,diagnostic_sequence=False,design=None):
    """Legal chip ownership drives one warm incremental package trajectory."""
    scenario_parameters={key:value for key,value in locals().items() if key not in ('contract','design')}
    if tx_fpga_preemphasis is None:
        selected_design=b.design_for_contract(contract,design)
        tx_fpga_preemphasis=wideband and selected_design.architecture['rf_interoperability'].get('fpga_tx_preparation',{}).get('wideband_correction_enabled',False)
    if type(tx_fpga_preemphasis) is not bool or (tx_fpga_preemphasis and not wideband):
        raise ValueError('FPGA TX correction requires the explicit wideband record')
    if diagnostic_sequence and (wideband or packet_rx or turnaround or packet_reply):
        raise ValueError('Diagnostic lifecycle requires the normal retained-state schedule')
    if wired_noise_control not in ('nominal','detector_off','voltage_off','both_off','detector_half','voltage_half'):raise ValueError('Unknown diagnostic noise control')
    if not np.isfinite(stress_ripple_peak_v) or stress_ripple_peak_v<0:raise ValueError('Finite nonnegative ripple amplitude required')
    if not np.isfinite(stress_ripple_hz) or stress_ripple_hz<=0:raise ValueError('Positive finite ripple frequency required')
    lo_hz=2.402e9 if packet_rx else 2.4e9
    if packet_rx and (wideband or turnaround):raise ValueError('Packet case uses dedicated RF source')
    if not 0<tx_native_peak<=511:raise ValueError('TX native peak must fit signed DAC')
    if lo_divider not in (64,128,256,512):raise ValueError('Supported external LO divider required')
    import copy
    from converter_dynamics import discharged_sar_state,parameters_from_inventory,recover
    from selected_rf import native_dac,analog_hold_at,receive_frontend,receive_supply_reference,receive_gain_elasticity,analog_filter,he_source,he_observation,transmit_output,tx_amplitude_bound,analog_modes,tx_supply_gain
    from behavioral import bandlimited_samples
    from robustness_envelope import LocalLoadTransient
    design=b.design_for_contract(contract,design)
    if diagnostic_sequence:
        design=design.hypothetical(reason='Diagnostic reference loading experiment',changes={
            'model_assumptions.paired_sar.parameters.diagnostic_reference_effective_cap_per_lane_f':.25e-12})
    architecture=design.architecture
    gain=max(set(architecture['blocks']['pga_i']['parameters']['gain_db']) &
             set(architecture['blocks']['pga_q']['parameters']['gain_db']))
    configs=dict(rf_rx=design.configure(engine='rf',direction='rx',reference_hz=lo_hz,sample_divider=lo_divider,pga_gain_db=gain),
        rf_tx=design.configure(engine='rf',direction='tx',reference_hz=lo_hz,sample_divider=lo_divider,tx_gain=tx_nominal_gain),
        wired=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8))
    context=dict(design_provenance=design.provenance(),
        resolved_configurations={key:value.record() for key,value in configs.items()},
        lifecycle_stimuli=scenario_parameters,
        unresolved_configurations=[])
    rf=b.configured_environment(configs['rf_rx'])
    pga_peak=receiver_pga_peak(rf)
    context['pga_nominal_peak_limit_v']=pga_peak
    for name in ('adc_i','adc_q'):
        adc=architecture['blocks'][name]['parameters']
        if (adc['native_bits'],adc['transport_bits'])!=(10,12):
            raise ValueError('Lifecycle ADC adapter requires native 10-bit and transport 12-bit words')
    tx_nominal_gain=configs['rf_tx'].resolved_tx_gain
    rf_tx=b.configured_environment(configs['rf_tx'])
    wire=b.configured_environment(configs['wired'])
    driver=architecture['blocks']['rfdriver']['parameters']
    dac_scale=architecture['blocks']['dac_i']['parameters']['differential_peak_v']
    for name in ('dac_i','dac_q'):
        dac=architecture['blocks'][name]['parameters']
        if (dac['native_bits'],dac['transport_bits'])!=(10,12) or dac['differential_peak_v']!=dac_scale:
            raise ValueError('Lifecycle DAC adapter requires matched 10-bit/12-bit converters')
    if not driver['gain_range'][0]<=tx_nominal_gain<=driver['gain_range'][1]:
        raise ValueError('Lifecycle TX gain outside the design range')
    if (turnaround or packet_reply) and rf['ledger']['owner_current_a']!=rf_tx['ledger']['owner_current_a']:
        raise ValueError('Warm RF direction sequence requires matching inventory loads or explicit direction load scheduling')
    timing=contract['physical_services']['external_clock_input']
    stress,sensitivity,disturbance=shared_supply_disturbance(timing,
        shared_stress=shared_stress,stress_ripple_peak_v=stress_ripple_peak_v,
        stress_ripple_hz=stress_ripple_hz)
    rail=LocalLoadTransient(rf['network'],clock_pole_hz=timing['supply_delay_pole_hz'],
                           clock_sensitivity_s_per_v=sensitivity,include_host_load=True)
    chip=BehavioralChip(selected_transport_assumptions(rf))
    chip.attach_analog_qualification([(0.,False)],max_age_s=qualification_max_age_s)
    baseline=rf['ledger']['local_branch_current_a'];rows=[];fault_gap=None;fault_epoch=None
    parameters=parameters_from_inventory(architecture)
    diagnostic_observations=[]
    condition_generation=0;calibration_fault_events=[]
    from rf_power_calibration import validate_calibration_generation
    comparator_model=dict(architecture['model_assumptions']['paired_sar_comparator']['parameters'])
    context['comparator_model']=comparator_model
    converter_state=discharged_sar_state(parameters=parameters,comparator_model=comparator_model);rail_history=[]
    reference_target=architecture['blocks']['refbuf']['parameters']['target_v']
    context['reference_target_v']=reference_target
    reference_targets=[(0.,reference_target)]
    tx_edges=[0.];tx_values=[0j]
    tx_supply_state={}
    tx_supply_quiet_samples=0
    filters=lifecycle_filter_settings(design,1e6 if packet_rx else None,None if wideband else 3e6)
    context['filter_configuration']=filters
    tx_cutoff=filters['tx_cutoff_hz']
    tx_family,tx_order=lifecycle_tx_filter(design)
    context['tx_reconstruction']=dict(family=tx_family,order=tx_order)
    tx_amplitude_requirement=tx_amplitude_bound(
        contract['generic_configuration_target']['tx_amplitude_operating_requirement'],
        nominal_gain=tx_nominal_gain,gain_reference_v=driver['gain_reference_v'],
        driver_parameters=driver,output_parameters=rf_tx['rf_output_parameters'],
        reconstruction_family=tx_family)
    tx_native_history_bound=tx_amplitude_requirement['sufficient_native_complex_code_radius']
    tx_residues,tx_poles=analog_modes(tx_family)
    tx_modes=np.zeros(len(tx_poles),complex);tx_filter_time=0.;tx_hold=0j
    rx_filter_state=None;rx_filter_time=0.;rx_noise=np.random.default_rng(901)
    rx_cutoff=filters['rx_cutoff_hz'];rx_gain=10**(configs['rf_rx'].pga_gain_db/20)
    wave,rf_drive=he_source(oversample=16,symbols=4) if wideband else (None,None)
    if packet_rx:
        from protocol_signals import ble_advertising_bits,gfsk
        packet_pdu=bytes.fromhex('c30c0102030405c1a6a5a4a3a2c1' if packet_request else '0206010203040506')
        packet_bits=ble_advertising_bits(packet_pdu,37)
        packet_wave=gfsk(packet_bits,rate=1e6,h=.5,fs=320e6)
        rf_drive=packet_wave.samples
    rf_launch=0.
    reference_ledger=dict(initial_v=converter_state['reference_v'],idle_recharge_c=0.,
        sar_recharge_c=0.,sar_draw_c=0.,sar_conversions=0,source_peak_a=0.)
    def reference_accounting():
        supplied=reference_ledger['idle_recharge_c']+reference_ledger['sar_recharge_c']
        stored=parameters.reference_cap_f*(converter_state['reference_v']-reference_ledger['initial_v'])
        residual=supplied-reference_ledger['sar_draw_c']-stored
        assert abs(residual)<1e-21
        end=converter_state['end_time_s']
        return dict(**reference_ledger,accounted_until_s=end,final_v=converter_state['reference_v'],
            total_signed_recharge_c=supplied,stored_charge_change_c=stored,
            balance_residual_c=residual,source_mean_a=supplied/end if end else 0.,
            conversion_activity_fraction=(reference_ledger['sar_conversions']/(lo_hz/lo_divider)/end if end else 0.),
            same_code_statistics_continuous_sar_draw_a=(reference_ledger['sar_draw_c']/reference_ledger['sar_conversions']*(lo_hz/lo_divider) if reference_ledger['sar_conversions'] else 0.),
            source_plus_idle_peak_a=reference_ledger['source_peak_a']+parameters.reference_idle_a,
            reserved_source_plus_idle_a=parameters.reference_limit_a+parameters.reference_idle_a,
            scope='One retained reservoir across all modeled idle, SAR and TX-reference-observation intervals, including startup and fault recovery. Repeated boundary observations do not recharge twice. Native TX DAC reference draw is still unmodeled, so this is conservation of represented loads, not total reference power closure or package-current feedback.')
    def snapshot():
        saved=copy.copy(rail);saved.state=rail.state.copy();saved._transitions=dict(rail._transitions)
        rail_history.append(saved)
    def rail_at(times,*,delay=False):
        times=np.asarray(times,float);result=np.empty(times.size)
        for index in np.argsort(times.ravel()):
            time=float(times.ravel()[index])
            prior=next((x for x in reversed(rail_history) if x.time<=time),None)
            if prior is None:raise ValueError('Missing retained package history for converter')
            forecast=copy.copy(prior);forecast.state=prior.state.copy();forecast._transitions=dict(prior._transitions)
            forecast.advance(time)
            result[index]=(forecast.clock_delay if delay else rf['ledger']['local_payload_clock_core_rail_v']+forecast.voltage)
        return result.reshape(times.shape)+disturbance(times,delay=delay)
    def rx_filter_to(time,*,active):
        nonlocal rx_filter_state,rx_filter_time
        duration=time-rx_filter_time
        if duration<0:raise ValueError('RF filter reversed time')
        if duration==0:raise ValueError('RF filter requires forward observation')
        count=max(1,int(np.ceil(duration*320e6))) if active else 1
        dt=duration/count;times=rx_filter_time+(np.arange(count)+.5)*dt
        if active:
            rails=rail_at(times)
            if wideband or packet_rx:
                position=(times-rf_launch)*320e6
                drive=np.interp(position,np.arange(len(rf_drive)),rf_drive.real,left=0.,right=0.)+1j*np.interp(position,np.arange(len(rf_drive)),rf_drive.imag,left=0.,right=0.)
            else:drive=np.exp(2j*np.pi*1e6*times)
            forcing,_=receive_frontend(drive,times,rails,
                -2*np.pi*lo_hz*rail_at(times,delay=True),sample_hz=1/dt,
                wanted_dbm=-65.,blocker_dbm=-50.,noise_rng=rx_noise,
                gain_reference_v=receive_supply_reference(rf,'gain_reference_v'),gain_supply_elasticity=receive_gain_elasticity(rf),early_gain_db=configs['rf_rx'].lna_gain_db,temperature_k=parameters.temperature_k,noise_figure_db=architecture['blocks']['lna']['parameters']['noise_figure_db'],
                input_iip3_dbm=architecture['blocks']['lna']['parameters']['iip3_dbm'])
            if chip.rf_direction_events is not None:
                forcing*=np.array([chip.rf_rx_analog_enabled_at(float(t)) for t in times])
        else:forcing=np.zeros(count,complex)
        capture={}
        filtered=analog_filter(forcing,1/dt,family='rx_finite_zero',cutoff_hz=rx_cutoff,
            initial_state=rx_filter_state,state_capture=capture)
        rx_filter_state=capture;rx_filter_time=time
        value=filtered[-1]*rx_gain;headroom=pga_peak*float(rail_at(np.array([time]))[0])/receive_supply_reference(rf,'headroom_reference_v')
        return complex(np.clip(value.real,-headroom,headroom),np.clip(value.imag,-headroom,headroom))
    def reference_idle_to(time,*,commit=True):
        nonlocal converter_state
        start=converter_state['end_time_s']
        if time<start:raise ValueError('TX reference observation reversed analog time')
        count=max(1,int(np.ceil((time-start)/1e-6)))
        edges=np.linspace(start,time,count+1)
        if len(reference_targets)>1:
            edges=np.unique(np.r_[edges,[t for t,_ in reference_targets if start<t<time]])
        rails=rail_at((edges[:-1]+edges[1:])/2)
        ref=converter_state['reference_v'];dac=complex(*converter_state['dac'])
        floor,ceiling=converter_supply_window(contract)
        for lo,hi,voltage in zip(edges[:-1],edges[1:],rails):
            target=next(value for when,value in reversed(reference_targets) if when<=(lo+hi)/2)
            if not floor<=voltage<=ceiling:raise AnalogQualificationError('Reference recovery left modeled supply range')
            if commit and hi>lo:
                reference_ledger['source_peak_a']=max(reference_ledger['source_peak_a'],
                    min(parameters.reference_limit_a,abs(target-ref)/(parameters.reference_r_ohm*3.3/voltage)))
            ref,dac,charge=recover(ref,dac,target,complex(*converter_state['last_code']),hi-lo,
                r=parameters.reference_r_ohm*3.3/voltage,c=parameters.reference_cap_f,
                limit=parameters.reference_limit_a,tau=parameters.dac_tau_s*3.3/voltage)
            if commit:reference_ledger['idle_recharge_c']+=charge
        if commit:converter_state=dict(converter_state,reference_v=float(ref),dac=[dac.real,dac.imag],end_time_s=float(time))
        return ref
    def observe_parked_reference(time):
        reference=reference_idle_to(time,commit=False)
        voltage=float(rail_at(np.array([time]))[0])
        low,high=contract['physical_services']['sar_timing']['startup']['model_reference_window_v']
        floor,ceiling=converter_supply_window(contract)
        return bool(low<=reference<=high and floor<=voltage<=ceiling)
    def reconstructed(time):
        nonlocal tx_modes,tx_filter_time
        if time<tx_filter_time:raise ValueError('TX filter reversed time')
        exponent=tx_poles*2*np.pi*tx_cutoff*(time-tx_filter_time)
        tx_modes=tx_modes*np.exp(exponent)+tx_hold*np.expm1(exponent)/tx_poles
        tx_filter_time=time
        return complex(np.sum(tx_residues*tx_modes))
    snapshot()
    if direct_usb:
        from protocol_pad import SharedWiredPad
        chip.attach_wired_pad(SharedWiredPad.from_architecture(architecture),rail_source=lambda t:float(rail_at(np.array([t]))[0]),
                             max_step_s=100e-9)
    for stage_index,(engine,directions) in enumerate((('rf',('rx',)),('rf',('tx',)),('wire',('rx','tx')),('rf',('rx',)),('rf',('tx',)),('rf',('tx',)),('rf',('rx',)))):
        reply_stage=packet_reply and stage_index==0
        reply_execution=None;reply_host=[];reply_control=dict(ready=False,launch_s=float("inf"),available_after_s=float("inf"))
        tdd_stage=turnaround and stage_index==0
        if reply_stage:directions=("rx","tx")
        if tdd_stage:directions=('rx','tx')
        converter_before=copy.deepcopy(converter_state)
        if stage_index==2 and wired_recovery:
            start=chip.time
            rail.ramp_to(start,wire['ledger']['local_branch_current_a']-baseline,100e-9,
                host_increment_a=wire['ledger']['host_node_current_a']-rf['ledger']['host_node_current_a'])
            snapshot()
            recovery=loaded_wired_recovery(contract,chip=chip,design=design,
                rail_voltage=lambda t:rail_at(np.array([t]))[0],
                rail_delay=lambda t:rail_at(np.array([t]),delay=True)[0],
                analog_observer=observe_parked_reference if independent_analog_observations else None)
            reference_idle_to(chip.time);rail.advance(chip.time)
            old=chip.epoch;discarded=chip.stop()
            rows.append(dict(engine='wire',directions=['rx'],fault=None,
                wired_recovery=recovery,wired_analog_cdr=None,wired_tx_electrical=None,
                rf_quality=None,tx_rf_port=None,epoch=old,start_s=start,end_s=chip.time,
                converter=dict(initial_state=converter_before,final_state=copy.deepcopy(converter_state)),
                state_retained_at_stop=True,discarded=discarded,
                scope='Recovery branch exercises wired RX; no simultaneous wired TX proof. Same chip, retained package and converter reservoir as surrounding RF stages.'))
            continue
        if stage_index==5:
            chip.advance(fault_gap[1]+100e-9);rail.advance(chip.time)
        if engine=='rf':
            chip.configure_numeric(engine='rf',rf=dict(sample_hz=configs['rf_rx'].sample_hz,
                sample_clock_source='external_lo',lo_hz=lo_hz,lo_divider=lo_divider,
                rx_cutoff_hz=rx_cutoff,tx_cutoff_hz=tx_cutoff))
            rate,bits=lo_hz/lo_divider,24;budget=rf_tx if directions==('tx',) else rf
        else:
            chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=configs['wired'].line_rate_bps))
            rate,bits=250e6,10;budget=wire
        input_codes=(1,1) if diagnostic_sequence and stage_index==0 else (2,3) if diagnostic_sequence and stage_index==3 else (0,0)
        chip.configure_converter_input_test(*input_codes)
        assert chip.stream is None
        chip.a=selected_transport_assumptions(budget)
        before=rail.state.copy();start=chip.time
        rail.ramp_to(start,budget['ledger']['local_branch_current_a']-baseline,100e-9,
            host_increment_a=budget['ledger']['host_node_current_a']-rf['ledger']['host_node_current_a'])
        np.testing.assert_array_equal(rail.state,before)
        snapshot()
        if stage_index==4:
            fault_gap=(chip.time+chip.a.startup_s+3e-6,chip.time+chip.a.startup_s+4e-6)
            # Cover remaining RF guards and both USB guards when enabled.
            # The old fixed edge count could imitate source failure solely
            # because a supplied design selected a longer startup guard.
            monitor_period=64/lo_hz
            monitor_span=max((20000 if wideband or packet_rx else 5000)*monitor_period,
                             (3+2*int(direct_usb))*chip.a.startup_s+60e-6)
            context['reference_stimulus_horizon_s']=monitor_span
            monitor_nominal=chip.time+np.arange(1,int(np.ceil(monitor_span/monitor_period))+1)*monitor_period
            monitor=rail.preview_clock_edges(monitor_nominal)+disturbance(monitor_nominal,delay=True)
            monitor=monitor[(monitor<fault_gap[0])|(monitor>=fault_gap[1])]
            chip.attach_reference(monitor,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
        chip.configure_transport('exclusive')
        reference_idle_to(chip.time)
        def observe_validity(time,reference,low_rail,high_rail):
            low,high=contract['physical_services']['sar_timing']['startup']['model_reference_window_v']
            floor,ceiling=converter_supply_window(contract)
            valid=bool(low<=np.min(reference) and np.max(reference)<=high and low_rail>=floor and high_rail<=ceiling)
            chip.analog_qualification.observe(float(time),valid)
            return valid
        v=float(rail_at(np.array([chip.time]))[0])
        observe_validity(chip.time,converter_state['reference_v'],v,v)
        chip.start();armed=chip.time
        while chip.state=='acquiring':
            next_time=min(chip.time+100e-9,chip.ready_at)
            chip.advance(next_time);rail.advance(next_time)
            reference=reference_idle_to(next_time);v=float(rail_at(np.array([next_time]))[0])
            observe_validity(next_time,reference,v,v)
            chip.advance(next_time)
            if chip.time-armed>100e-6:raise ValueError('Analog qualification did not complete')
        assert chip.state=='active'
        analog_ready_at=chip.time
        origin=chip.time
        rf_launch=origin+(8e-6 if packet_rx else 2e-6)
        direction_actions=[]
        if reply_stage:chip.enable_rf_direction_gate(rx_completion_latency_s=sum(parameters.bit_durations_s))
        if tdd_stage:
            chip.enable_rf_direction_gate(rx_completion_latency_s=sum(parameters.bit_durations_s))
            direction_actions.append(chip.schedule_rf_direction('tx',at_s=origin+1e-6,settle_s=2e-6))
            direction_actions.append(chip.schedule_rf_direction('rx',at_s=origin+6e-6,settle_s=2e-6))
        if engine=='rf' and 'rx' in directions:
            rx_filter_to(origin,active=False)
        nominal=origin+np.arange(1,8193 if reply_stage else 4097)/rate
        if fault_gap is not None:
            nominal=nominal[(nominal<fault_gap[0])|(nominal>=fault_gap[1])]
        completion_delay=sum(parameters.bit_durations_s) if engine=='rf' and 'rx' in directions else 0.
        edges=rail.preview_clock_edges(nominal)+disturbance(nominal,delay=True)-origin+completion_delay
        clock_event=rail.bind_clock_events(nominal,origin=origin)
        event=chip.bind_stream_callback(lambda index:clock_event(index)+float(disturbance(nominal[index],delay=True))+completion_delay)
        depth=contract['transport']['scheduling']['ingress_bits_per_source']
        sent=[];received=[];received_nominal_times=[];prefill=0 if tdd_stage or reply_stage else 512;conversions=[];tx_conversions=[]
        tx_filter_before=reconstructed(origin)
        source=lambda index:(index*73+19)&1023
        tx_preparation=None
        if wideband and engine=='rf' and 'tx' in directions:
            # 512 prefill bits plus 16 host padding bits align the first I/Q
            # word at sample index 22; first physical event is index 0 at 1/fs.
            planned=(np.arange(4096)+23)/rate
            prepared=bandlimited_samples(wave.samples,(planned-2e-6)*20e6,32)
            scale=tx_native_peak/max(float(np.max(abs(prepared))),1e-30)
            correction=None
            if tx_fpga_preemphasis:
                from selected_rf import fpga_tx_filter_correction
                prepared,correction=fpga_tx_filter_correction(prepared,sample_hz=rate,
                    filter_family=tx_family,cutoff_hz=tx_cutoff,
                    **{key:architecture['rf_interoperability']['fpga_tx_preparation'][key]
                       for key in ('taps','coefficient_fraction_bits')})
            codes=np.stack((np.rint(prepared.real*scale),np.rint(prepared.imag*scale)),axis=-1).astype(int)
            radius=np.sqrt(np.sum(codes.astype(float)**2,axis=1))
            if np.any(codes < -512) or np.any(codes > 511):
                raise ValueError('FPGA-corrected TX record exceeds native DAC range; reduce requested amplitude')
            if not tx_fpga_preemphasis:
                assert max(radius)<=tx_native_peak+2**-.5
            packed=[((int(i)*4)&4095)|(((int(q)*4)&4095)<<12) for i,q in codes]
            payload=[0]*16+[(word>>bit)&1 for word in packed for bit in range(24)]
            payload += [0]*((-len(payload))%10)
            host=[sum(payload[j+k]<<k for k in range(10)) for j in range(0,len(payload),10)]
            source=lambda index:host[index] if index<len(host) else 0
            tx_preparation=dict(fpga_preemphasis=correction,
                requested_uncorrected_native_peak=tx_native_peak,
                native_complex_code_peak=float(max(radius)),native_scale=scale,
                all_history_code_bound_pass=bool(max(radius)<=tx_native_history_bound),
                all_history_code_radius_bound=tx_native_history_bound,
                amplitude_proof_scope="Sampled waveform check only when all-history code bound fails; continuous overshoot and unseen history remain unqualified",
                host_alignment_padding_bits=16,initial_prefill_bits=prefill,
                reconstruction_cutoff_hz=tx_cutoff,scale_before_transport=True)
        args=dict(mode=1,source_hz=rate,sample_bits=bits,epoch=chip.epoch,frames=(1000 if packet_request else 800) if packet_rx and engine=='rf' and 'rx' in directions else 64 if tdd_stage else 320 if wideband and engine=='rf' and stage_index!=4 else 16,
                  directions=directions,depth_bits=depth)
        if independent_analog_observations:
            def observe_idle(time):
                # RX conversion observations own intervals with in-flight SAR activity.
                if engine=='rf' and 'rx' in directions and (chip.rf_direction_events is None or
                        chip._rf_direction_at(time-completion_delay)=='rx'):
                    return None
                return observe_parked_reference(time)
            args.update(analog_observer=chip.bind_stream_callback(observe_idle),
                        analog_observation_period_s=100e-9)
        args['tx_event_time' if 'tx' in directions else 'rx_event_time']=event
        if tdd_stage:
            args['rx_event_time']=event
            args['tx_event_time']=chip.bind_stream_callback(clock_event)
            args['tx_host_enable']=lambda time,index:index<64 or origin+3e-6<=time<origin+6e-6
            packed=(32&4095)|((-16&4095)<<12)
            source=lambda index:((packed|(packed<<24))>>((index*10)%24))&1023
        if reply_stage:
            source=lambda index:reply_host[index] if index<len(reply_host) else 0
            args['rx_event_time']=event
            args['tx_event_time']=chip.bind_stream_callback(clock_event)
            args['tx_host_enable']=lambda time,index:reply_control['ready'] and time>=reply_control['available_after_s'] and (index<77 or time>=reply_control['launch_s'])
        if 'tx' in directions:
            def observe_tx(time,word):
                nonlocal tx_hold
                reference=reference_idle_to(time)
                voltage=float(rail_at(np.array([time]))[0])
                if not observe_validity(time,reference,voltage,voltage):
                    raise AnalogQualificationError('TX reference/supply observation invalidates payload')
                sent.append((time,word))
                if engine=='rf':
                    raw=np.array([[word&4095,(word>>12)&4095]],dtype=np.int64)
                    raw=np.where(raw>=2048,raw-4096,raw)
                    analog,conversion=native_dac(raw,np.array([reference/reference_target*dac_scale]))
                    filtered=reconstructed(time);tx_hold=complex(analog[0])
                    tx_edges.append(float(time));tx_values.append(tx_hold)
                    tx_conversions.append(dict(time_s=float(time),reference_v=reference,
                        native_dac_v=[float(analog[0].real),float(analog[0].imag)],
                        filtered_v=[filtered.real,filtered.imag],
                        saturated_components=conversion['saturated_components']))
            args.update(tx_source=chip.bind_stream_callback(source),tx_prefill_bits=prefill,
                tx_word_observer=observe_tx)
        if 'rx' in directions:
            convert=chip.bind_sar_converter(parameters=parameters,comparator_model=comparator_model) if engine=='rf' else None
            def rx_source(index):
                nonlocal converter_state
                if engine=='rf':
                    sample_time=origin+edges[index]-sum(parameters.bit_durations_s)
                    beginning=rx_filter_to(sample_time-parameters.acquisition_s,active=True)
                    ending=rx_filter_to(sample_time,active=True)
                    values,report,trace=convert(np.array([ending]),
                        np.array([beginning]),np.array([sample_time]),
                        lambda times:np.full_like(times,reference_target,dtype=float),rail_at,
                        initial_state=converter_state,idle_step_s=1e-6)
                    assert report['initial_reference_v']==converter_state['reference_v']
                    assert abs(report['reference_charge_balance_residual_c'])<1e-22
                    assert trace['final_state']['end_time_s']<=origin+edges[index]+1e-15
                    converter_state=trace['final_state'];conversions.append(report)
                    reference_ledger['sar_recharge_c']+=report['signed_reference_recharge_c']
                    reference_ledger['sar_draw_c']+=report['reference_charge_drawn_c']
                    reference_ledger['sar_conversions']+=1
                    reference_ledger['source_peak_a']=max(reference_ledger['source_peak_a'],report['reference_source_peak_a'])
                    if not observe_validity(origin+edges[index],[report['first_acquisition_reference_v'],*report['decision_reference_interval_v']],
                            *report['evaluated_supply_interval_v']):
                        raise AnalogQualificationError('Converter observation invalidates payload')
                    word=(int(values[0,0])&4095)|((int(values[0,1])&4095)<<12)
                else:word=(index*131+37)&((1<<bits)-1)
                received_nominal_times.append(origin+(index+1)/rate)
                received.append(word);return word
            args['rx_source']=chip.bind_stream_callback(rx_source)
        wired_receiver=None;wired_acceptance=[];wired_bit_observations=[]
        if wired_cdr and engine=='wire':
            from wired_envelope import physical_receiver
            stimulus=np.random.default_rng(9021).integers(0,2,12000).tolist()
            if wired_encoded:
                from protocol_signals import pcie_gen1_compliance_bits
                stimulus=pcie_gen1_compliance_bits(300)
            stimulus[4000:4400]=[0]*400  # Transition drought: explicit lock-loss stimulus.
            receiver_requirement=contract['physical_services']['wired_receiver']
            impairment=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0. if wired_noise_control in ('voltage_off','both_off') else receiver_requirement['post_equalizer_disturbance_rms_v']*(.5 if wired_noise_control=='voltage_half' else 1.),offset_v=receiver_requirement['post_equalizer_offset_v'],
                delay_tones=[],rail_tones=[],signal_scale=budget['ledger']['local_payload_clock_core_rail_v']/b.wired_gain_reference(budget),
                rail_dc_v=budget['ledger']['local_payload_clock_core_rail_v'],
                rail_at_s=lambda t:float(rail_at(np.array([origin+t]))[0]),
                delay_at_s=lambda t:float(rail_at(np.array([origin+t]),delay=True)[0]))
            if wired_equalized:
                impairment.update(ctle_zero_s=receiver_requirement['ctle_zero_s'],ctle_pole_s=receiver_requirement['ctle_pole_s'])
            wired_receiver=physical_receiver(stimulus,2.5e9,.35,100.,receiver_requirement['driver_tau_s'],receiver_requirement['pad_cap_f'],impairment)
            wired_receiver.detector_noise_rms_s=receiver_requirement['detector_noise_rms_s']
            if wired_noise_control in ('detector_off','both_off'):wired_receiver.detector_noise_rms_s=0.
            elif wired_noise_control=='detector_half':wired_receiver.detector_noise_rms_s*=.5
            wired_receiver.bit_observer=lambda bit,qualified:wired_bit_observations.append((bit,qualified))
            def cdr_valid(index):
                qualified=all(valid for _,valid in wired_receiver.predicted[1])
                wired_receiver.commit(index);wired_acceptance.append(qualified)
                return bool(qualified)
            def cdr_consume(index):
                word=wired_receiver.consume(index)
                if wired_acceptance[-1]:received.append(word)
                return word
            args.update(fault_on_rx_loss=wired_fail_closed,rx_event_time=chip.bind_stream_callback(wired_receiver.forecast),
                rx_valid=chip.bind_stream_callback(cdr_valid),rx_source=chip.bind_stream_callback(cdr_consume))
        if stage_index==5:
            try:chip.transfer(**dict(args,epoch=fault_epoch))
            except ValueError:pass
            else:raise AssertionError('Pre-fault epoch accepted after recovery')
        flow=chip.transfer(**args)
        if flow['fault'] is not None:
            condition_generation+=1
            calibration_fault_events.append(dict(time_s=chip.time,epoch=chip.epoch,
                reason=flow['fault'],condition_generation=condition_generation))
        if stage_index==4:
            assert flow['fault']=='reference_lost' and chip.state=='fault'
            assert fault_gap[0]<=chip.time<=fault_gap[0]+110e-9
            fault_epoch=chip.epoch
            emitted_at_fault=len(sent)
            try:chip.transfer(**args)
            except ValueError:pass
            else:raise AssertionError('Faulted chip accepted payload service')
            assert len(sent)==emitted_at_fault

        elif flow['fault'] is not None:
            rail.advance(chip.time)
            return dict(context,shared_supply_stress=stress,wanted_waveform='le_1m_advertising_packet' if packet_rx else 'four_he20_data_symbols' if wideband else 'one_mhz_tone',reference_charge_accounting=reference_accounting(),rf_sample_hz=lo_hz/lo_divider,lo_divider=lo_divider,status='rejected_by_rx_qualification' if flow['fault']=='rx_qualification_lost' else 'rejected_by_reference_monitor' if flow['fault']=='reference_lost' else 'rejected_by_analog_qualification',stages=rows,
                failed_stage=dict(index=stage_index,engine=engine,directions=list(directions),
                    fault=flow['fault'],time_s=chip.time,produced_bits=flow['produced_bits'],
                    delivered_words=len(chip.stream.get('rx_words',[])),
                    rx_ever_qualified=chip.stream.get('rx_ever_qualified',False),
                    wired_cdr_word_index=None if wired_receiver is None else wired_receiver.word_index,
                    last_conversion=conversions[-1] if conversions else None,
                    retained_converter_state=copy.deepcopy(converter_state)),
                analog_qualification_events=list(zip(chip.analog_qualification.times,chip.analog_qualification.valid)),
                analog_qualification_max_age_s=qualification_max_age_s,
                last_analog_observation_s=chip.analog_qualification.observation_times[-1],
                analog_observation_age_at_fault_s=chip.time-chip.analog_qualification.observation_times[-1],
                scope='The recorded live stream fault rejected this lifecycle; later stages were not executed. RX qualification loss stops delivery after acquisition instead of concatenating separated fragments. Reference, supply and CDR validity are model observations, not physical sensing/status transport or a fault-latency guarantee. Converter charge/RNG and receiver state reached before the fault are retained; prior successes do not qualify the rejected continuation.')
        tx_payload_bits=0;rx_payload_bits=0;host_iq=None;rf_quality=None
        if 'tx' in directions and not reply_stage:
            actual=[(word>>bit)&1 for _,word in sent for bit in range(bits)]
            expected=[0]*prefill+[(source(i)>>bit)&1 for i in range(10000) for bit in range(10)]
            assert len(actual)>prefill and actual==expected[:len(actual)]
            if tdd_stage:
                expected_tx=origin+edges-completion_delay
                expected_tx=expected_tx[(expected_tx>=origin+3e-6)&(expected_tx<origin+6e-6)]
                np.testing.assert_allclose([time for time,_ in sent],expected_tx[:len(sent)],rtol=0,atol=1e-15)
            else:
                np.testing.assert_allclose([time for time,_ in sent],origin+edges[:len(sent)],rtol=0,atol=1e-15)
            if fault_gap is not None:
                assert all(not fault_gap[0]<=time<fault_gap[1] for time,_ in sent)
            tx_payload_bits=len(actual)-prefill
        if 'rx' in directions:
            actual=[(word>>bit)&1 for word in chip.stream['rx_words'] for bit in range(10)]
            expected=[(word>>bit)&1 for word in received for bit in range(bits)]
            assert actual and actual==expected[:len(actual)]
            rx_payload_bits=len(actual)
            if engine=='rf':
                delivered,partial=delivered_iq_words(chip.stream['rx_words'])
                source_iq=np.array([[(word&4095),((word>>12)&4095)]
                    for word in received[:len(delivered)]],dtype=np.int64)
                source_iq=np.where(source_iq>=2048,source_iq-4096,source_iq)
                np.testing.assert_array_equal(delivered,source_iq)
                host_iq=dict(complete_samples=len(delivered),partial_sample_bits=partial,
                    converted_samples=len(received),undelivered_complete_or_partial_samples=len(received)-len(delivered),
                    signed_iq_words=delivered.tolist(),
                    nominal_sample_times_s=received_nominal_times[:len(delivered)],
                    scope='Only complete samples reconstructed from actual 10-bit host words. Nominal FPGA timestamps exclude hidden package timing error; trailing partial sample is not padded or evaluated.')
                if diagnostic_sequence:
                    mean=np.mean(delivered,axis=0)
                    if input_codes==(1,1):assert np.max(abs(mean))<16
                    elif input_codes==(2,3):assert mean[0]>450 and mean[1]<-450
                    stale_rejected=False
                    if input_codes==(0,0) and diagnostic_observations:
                        try:validate_calibration_generation(diagnostic_observations[-1]['condition_generation'],condition_generation)
                        except ValueError:stale_rejected=True
                        else:raise AssertionError('Pre-fault diagnostic record became valid after recovery')
                    diagnostic_observations.append(dict(epoch=chip.epoch,condition_generation=condition_generation,
                        pre_fault_diagnostic_rejected=stale_rejected,input_codes=list(input_codes),
                        delivered_samples=len(delivered),mean_transport_codes=mean.tolist(),
                        diagnostic_reference_charge_c=sum(x['diagnostic_reference_charge_c'] for x in conversions)))
                if packet_rx:
                    from ble_packet import observe
                    normalized=(delivered[:,0]+1j*delivered[:,1])/2048
                    observer_times=np.arange(32/rate,(len(delivered)-33)/rate,1/10e6)
                    observed=bandlimited_samples(normalized,observer_times*rate-1,32,cutoff=min(1.,10e6/rate))
                    rf_quality=observe(observed,fs=10e6,channel=37)
                    rf_quality.update(source='actual_host_delivered_iq',fpga_lookahead_s=32/rate,
                        expected_pdu_matches=rf_quality.get('pdu_hex')==packet_pdu.hex(),
                        scope='One LE 1M advertising PDU at 2402 MHz, fixed gain/wanted/blocker. Receiver searches preamble/access address and checks CRC using delivered samples only; source truth is scoreboard-only. No PER, AGC, response or sensitivity qualification.')
                if packet_request:
                    from ble_packet import response_budget
                    from resource_configuration import validate_rf_settings
                    settings=validate_rf_settings(sample_hz=rate,tx_cutoff_hz=tx_cutoff,
                        rx_cutoff_hz=rx_cutoff,rx_filter_order=5,sample_clock_source='external_lo',
                        lo_hz=lo_hz,lo_divider=lo_divider)
                    observer_origin=origin+float(observer_times[0])
                    rf_quality['response_plan']=response_budget(rf_quality,settings,rf,contract,
                        advertiser_address=bytes.fromhex('a6a5a4a3a2c1'),
                        host_samples_ready_s=chip.time-observer_origin)
                    rf_quality['response_plan']['observer_origin_s']=observer_origin
                    rf_quality['response_plan']['actual_record_available_s']=chip.time
                    rf_quality['response_plan']['scope']+=' Uses the completed actual host record, conservatively waiting for its tail. No live TX action scheduled by this RX-only case.'
                if wideband:
                    observer_times=2e-6+np.arange(len(wave.samples))/20e6
                    coordinates=observer_times*rate-1
                    assert coordinates[-1]+32<len(delivered),'Insufficient delivered RF record for FIR lookahead'
                    normalized=(delivered[:,0]+1j*delivered[:,1])/2048
                    observed=bandlimited_samples(normalized,coordinates,32,cutoff=20e6/rate)
                    rf_quality=he_observation(wave,observed)
                    rf_quality.update(source='actual_host_delivered_iq',fpga_lookahead_s=32/rate,
                        scope='Four HE20 DATA symbols; first two known training, final two held out. Fixed gain, ideal frame boundary, no real preamble/CFO search/AGC or PER claim. No hidden clock or reference supplied to observer.')

        if reply_stage:
            plan=rf_quality['response_plan']
            assert plan['reply_armed'] and not sent
            decoded=bytes.fromhex(rf_quality['pdu_hex'])
            payload=decoded[8:14]+b'\x03\x09SV'
            response_pdu=bytes([0x44,len(payload)])+payload
            response_bits=ble_advertising_bits(response_pdu,37)
            response_wave=gfsk(response_bits,rate=1e6,h=.5,fs=40e6)
            trim=response_wave.metadata['delay']
            response_samples=response_wave.samples[trim:trim+len(response_bits)*40]
            # FPGA waveform generation uses nominal chip sample rate, not hidden edges.
            positions=np.arange(4096)/rate*40e6
            values=np.interp(positions,np.arange(len(response_samples)),response_samples.real,left=0.,right=0.)+1j*np.interp(positions,np.arange(len(response_samples)),response_samples.imag,left=0.,right=0.)
            native=np.stack((np.rint(values.real*50),np.rint(values.imag*50)),axis=-1).astype(int)
            packed=[((int(i)*4)&4095)|(((int(q)*4)&4095)<<12) for i,q in native]
            payload_bits=[(word>>bit)&1 for word in packed for bit in range(24)]
            payload_bits += [0]*((-len(payload_bits))%10)
            reply_host.extend(sum(payload_bits[j+k]<<k for k in range(10)) for j in range(0,len(payload_bits),10))
            launch=observer_origin+plan['target_air_start_s']
            # Use completed work+command+settle budget, then wait with clocks live.
            command_done=observer_origin+plan['ready_s']
            assert command_done>chip.time and launch>command_done
            epoch=chip.epoch
            direction_actions.append(chip.schedule_rf_direction('tx',at_s=command_done,settle_s=launch-command_done))
            reply_control.update(ready=True,launch_s=launch,available_after_s=command_done)
            frame_s=64/(312.5e6*chip.a.h2d_clock_scale)
            end=launch+len(response_bits)/1e6+10e-6
            flow=chip.transfer(**dict(args,frames=int(np.ceil((end-chip.time)/frame_s))))
            assert flow['fault'] is None and chip.epoch==epoch and sent
            assert all(time>=launch for time,_ in sent)
            actual=[(word>>bit)&1 for _,word in sent for bit in range(24)]
            expected=[(source(i)>>bit)&1 for i in range((len(actual)+9)//10) for bit in range(10)]
            assert actual==expected[:len(actual)]
            tx_payload_bits=len(actual)
            actual_rx=[(word>>bit)&1 for word in chip.stream['rx_words'] for bit in range(10)]
            expected_rx=[(word>>bit)&1 for word in received for bit in range(24)]
            assert actual_rx==expected_rx[:len(actual_rx)]
            rx_payload_bits=len(actual_rx)
            reply_execution=dict(epoch_preserved=True,request_record_available_s=plan['actual_record_available_s'],
                command_budget_complete_s=command_done,scheduled_launch_s=launch,first_dac_consumption_s=sent[0][0],
                response_pdu_hex=response_pdu.hex(),actual_tx_samples=len(sent),synthetic_prefill_bits=prefill,
                scope='Same live chip/clock/queues and retained analog state. Approved FPGA policy creates response words; no packet logic on chip. Command latency is budgeted, not decoded SPI. Ideal TX mute; air timing and RF waveform checked separately.')

        tx_port=None
        if engine=='rf' and 'tx' in directions:
            times=origin+np.arange(int(np.ceil((chip.time-origin)*320e6)))/320e6
            baseband=analog_hold_at(np.asarray(tx_values),np.asarray(tx_edges),times,
                family=tx_family,cutoff_hz=tx_cutoff)
            # Retain supply-rejection memory through quiet/RX/wired intervals.
            # Observe the same package history rather than settling to each new
            # packet's first rail. Bias startup/power-gating physics are separate.
            quiet_start=0. if not tx_supply_state else tx_supply_state['time_s']+1/320e6
            if quiet_start<times[0]:
                quiet_times=quiet_start+np.arange(int(np.ceil((times[0]-quiet_start)*320e6)))/320e6
                quiet_times=quiet_times[quiet_times<times[0]]
                if len(quiet_times):
                    tx_supply_gain(rail_at(quiet_times),driver['gain_reference_v'],driver,
                        quiet_times,state=tx_supply_state)
                    tx_supply_quiet_samples+=len(quiet_times)
            port,electrical,clipped=transmit_output(baseband,rail_at(times),
                -2*np.pi*lo_hz*rail_at(times,delay=True),nominal_gain=tx_nominal_gain,
                gain_reference_v=driver['gain_reference_v'],driver_parameters=driver,rail_bias_a=rf_tx['inventory_current_a']['rf'],
                output_parameters=rf_tx['rf_output_parameters'],times=times,supply_gain_state=tx_supply_state)
            if tdd_stage or reply_stage:
                enabled=np.array([chip._rf_direction_at(float(t))=='tx' for t in times])
                port['envelope_v']*=enabled;port['load_power_w']*=enabled
            amplitude=contract['generic_configuration_target']['tx_amplitude_operating_requirement']
            tx_port=dict(supply_gain_state=dict(tx_supply_state),
                supply_gain_quiet_samples=tx_supply_quiet_samples,
                supply_gain_scope='One retained held-input gain state, including sampled quiet-period rail history; initialized settled at first rail. Not cold bias startup or physical power-gating behavior.',
                nominal_gain_requirement=tx_nominal_gain,host_preparation=tx_preparation,amplitude_requirement=tx_amplitude_requirement,
                observed_reconstruction_peak_v=float(np.max(abs(baseband))),
                sampled_amplitude_exceedances=int(np.sum(abs(baseband)>amplitude['reconstructed_complex_peak_v'])),
                electrical=electrical,driver_current_clipped_samples=int(clipped.sum()),
                load_mean_power_w=float(np.mean(port['load_power_w'])),
                load_peak_envelope_v=float(np.max(abs(port['envelope_v']))),
                observed_samples=len(times),observation_hz=320e6,
                driver_bias_already_reserved_a=.028,
                scope='Actual consumed words through retained native DAC/reconstruction and shared mixer/driver/load. Active interval only; ideal mute at STOP/fault. No physical switching tail, TX noise, DAC charge/current feedback or protocol qualification.')
            if reply_stage:
                from ble_packet import observe
                peer_times=np.arange(launch-5e-6,times[-1],1/10e6)
                peer_samples=np.interp(peer_times,times,port['envelope_v'].real)+1j*np.interp(peer_times,times,port['envelope_v'].imag)
                peer=observe(peer_samples,fs=10e6,channel=37)
                reply_execution['peer']=peer
                reply_execution['peer_correct_response']=peer.get('pdu_hex')==response_pdu.hex() and peer.get('crc_ok',False)
                # Source truth is consulted only now, after response generation,
                # scheduling, actual transmission and independent demodulation.
                request_end=rf_launch+packet_wave.metadata['delay']/320e6+len(packet_bits)/1e6
                reply_execution['scoreboard_request_bit_end_s']=request_end
                reply_execution['scoreboard_first_dac_gap_s']=sent[0][0]-request_end
                if peer.get('acquired'):
                    peer_start=float(peer_times[0])+peer['start_sample']/10e6
                    reply_execution['scoreboard_peer_bit_start_s']=peer_start
                    reply_execution['scoreboard_interframe_s']=peer_start-request_end
                    reply_execution['scoreboard_error_from_150us_s']=peer_start-request_end-150e-6
                reply_execution['air_timing_scope']='Decoded bit-boundary diagnostic with ideal peer and 100 ns observation grid, not physical RF threshold/mask timing. RX/TX group delay calibration and switch tails remain unqualified; scoreboard source timing does not drive scheduling.'

                reply_execution['sampled_amplitude_exceedances']=tx_port['sampled_amplitude_exceedances']
                reply_execution['port_compliance']=electrical['within_declared_compliance']
                reply_execution['scope']+=' Independent ideal remote observer sees only actual RF output, with no response payload/start-time oracle; its 5 us prelaunch capture window is instrumentation, not a demodulator input.'
            if wideband and stage_index!=4:
                # Window is defined by the transmitted DATA record, never by an
                # amplitude threshold that would discard low-power samples.
                correction_delay=0. if tx_preparation['fpga_preemphasis'] is None else tx_preparation['fpga_preemphasis']['alignment_delay_s']
                active_start=origin+2e-6+correction_delay
                active_end=active_start+len(wave.samples)/20e6
                active=(times>=active_start)&(times<active_end)
                assert active.any() and active_end<=times[-1]
                active_power=float(np.mean(port['load_power_w'][active]))
                tx_port['data_interval_power']=dict(
                    start_s=active_start,end_s=active_end,samples=int(active.sum()),
                    mean_load_power_w=active_power,
                    mean_load_power_dbm=float(10*np.log10(max(active_power,1e-30)/1e-3)),
                    peak_to_mean_load_power_db=float(10*np.log10(max(float(np.max(port['load_power_w'][active])),1e-30)/max(active_power,1e-30))),
                    scope='Scheduled four-symbol DATA interval at the modeled resistive load, including waveform ramp/settling; excludes idle capture padding. Not antenna power, a complete packet, emissions qualification or a minimum useful-power requirement.')
                from selected_rf import tx_spectral_diagnostic
                tx_port['spectral_diagnostic']=tx_spectral_diagnostic(port['envelope_v'][active],320e6)
                from selected_rf import relative_burst_mask_screen
                tx_port['full_record_relative_mask_screen']=relative_burst_mask_screen(
                    port['envelope_v'],320e6,architecture['rf_interoperability']['tx_spectral_measurement'])
                tx_port['full_record_relative_mask_screen']['record_scope']='Entire stage at actual resistive-port output; ideal zero outside the stage models ideal mute. Four diagnostic DATA symbols, not complete HE PPDU or physical switch transients.'

                remote=analog_filter(port['envelope_v'],320e6,family='rx_all_pole_control',cutoff_hz=10e6)
                observer_times=active_start+np.arange(len(wave.samples))/20e6
                assert observer_times[-1]<times[-1]
                observed=np.interp(observer_times,times+1/320e6,remote.real)+1j*np.interp(observer_times,times+1/320e6,remote.imag)
                tx_port['quality']=he_observation(wave,observed)
                tx_port['quality']['source']='actual_consumed_host_words_to_independent_rf_observer'
                from selected_rf import he_scalar_observation
                tx_port['scalar_tx_observation']=he_scalar_observation(wave,observed,observer_cutoff_hz=10e6)
                tx_port['requirement_checks']=dict(
                    electrical=electrical['within_declared_compliance'],
                    no_driver_clipping=not bool(np.any(clipped)),
                    reconstructed_amplitude=tx_port['sampled_amplitude_exceedances']==0,
                    target_power=tx_port['data_interval_power']['mean_load_power_dbm']>=contract['generic_configuration_target']['tx_port_power_goal']['mean_load_power_dbm'])
                tx_port['requirements_met']=all(tx_port['requirement_checks'].values())

        wired_tx_audit=None
        if wired_tx_electrical and engine=='wire':
            from wired_envelope import physical_receiver
            nbits=2600
            tx_bits=[(word>>bit)&1 for _,word in sent for bit in range(10)][:nbits]
            assert len(tx_bits)==nbits
            ideal=origin+1/250e6+np.arange(nbits+1)/2.5e9
            actual_edges=ideal+rail_at(ideal,delay=True)
            np.testing.assert_allclose(actual_edges[:-1:10],[time for time,_ in sent[:nbits//10]],rtol=0,atol=1e-15)
            assert actual_edges[-1]<chip.time
            voltage=rail_at(actual_edges[:-1]);dc=budget['ledger']['local_payload_clock_core_rail_v']
            peer_impairment=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02,
                delay_tones=[],rail_tones=[],rail_dc_v=dc,signal_scale=dc/b.wired_gain_reference(budget),
                rail_modulation_location='driver',bit_drive_scale=voltage/dc,
                ctle_zero_s=200e-12,ctle_pole_s=80e-12)
            peer=physical_receiver(tx_bits,2.5e9,.35,100.,100e-12,2.7e-12,peer_impairment,
                source_edges_s=actual_edges-actual_edges[0])
            decisions=[];qualification=[]
            peer.bit_observer=lambda bit,valid:(decisions.append(bit),qualification.append(valid))
            for index in range(250):peer.forecast(index);peer.consume(index)
            lag=min(range(-3,4),key=lambda lag:sum(decisions[i]!=tx_bits[i+lag] for i in range(600,1200)))
            held=range(1200,2500)
            next_voltage=rail_at(actual_edges[1:])
            wired_tx_audit=dict(actual_emitted_bits=nbits,heldout_bits=1300,
                heldout_bit_errors=sum(decisions[i]!=tx_bits[i+lag] for i in held),
                heldout_qualified_fraction=float(np.mean(qualification[1200:])),
                final_peer_qualified=bool(peer.timing_qualified),offline_scoreboard_lag_bits=lag,
                max_word_boundary_error_s=float(max(abs(actual_edges[:-1:10]-np.array([t for t,_ in sent[:260]])))),
                maximum_adjacent_bit_rail_change_v=float(max(abs(next_voltage-voltage))),
                scope='First 2600 actual consumed/emitted bits, including the assumed zero prefill, drive nonuniform serializer boundaries consistent with every word event. Retained chip rail sets bit-held driver amplitude before exact two-pole/channel/peer-CTLE propagation. Independent peer CDR has its own phase/noise; source jitter is not canceled at peer aperture. Bit-held rail is an approximation, not continuous supply-noise closure. No pad clamp/current-steering/headroom, cable, internal serializer margin, power feedback, masks, idle/detection/OOB or protocol qualification.')

        wired_audit=None
        if wired_receiver is not None:
            accepted_indices=[i for i,valid in enumerate(wired_acceptance) if valid]
            # Offline bit score permits one fixed lag chosen only on early training.
            recovered=[bit for bit,_ in wired_bit_observations]
            lag=min(range(-3,4),key=lambda lag:sum(recovered[i]!=stimulus[i+lag] for i in range(600,1200)))
            delivered_count=len(chip.stream['rx_words'])
            held=[i for word in accepted_indices[:delivered_count] for i in range(word*10,word*10+10) if i>=1200]
            wired_audit=dict(selected_ctle_enabled=wired_equalized,ctle_zero_s=impairment.get('ctle_zero_s'),ctle_pole_s=impairment.get('ctle_pole_s'),noise_control=wired_noise_control,detector_noise_rms_s=wired_receiver.detector_noise_rms_s,voltage_disturbance_rms_v=impairment['noise_rms_v'],stimulus_kind='pcie_gen1_compliance_pattern' if wired_encoded else 'random_nrz',delivered_words=delivered_count,accepted_words=len(accepted_indices),rejected_words=len(wired_acceptance)-len(accepted_indices),
                qualification_losses=wired_receiver.qualification_losses,
                qualification_loss_bit_indices=[i for i in range(1,len(wired_bit_observations)) if wired_bit_observations[i-1][1] and not wired_bit_observations[i][1]],
                host_discontinuity_notification_modeled=False,first_qualified_bit=wired_receiver.first_qualified_bit,
                final_timing_qualified=bool(wired_receiver.timing_qualified),offline_fixed_lag_bits=lag,
                heldout_accepted_bits=len(held),heldout_bit_errors=sum(recovered[i]!=stimulus[i+lag] for i in held),
                accepted_before_drought=sum(i<400 for i in accepted_indices),
                accepted_after_drought=sum(i>=500 for i in accepted_indices),
                accepted_words_inside_drought=sum(410<=i<440 for i in accepted_indices),
                scope='Loaded 100 ps driver/2.7 pF pad receiver, causal sampled CDR and actual host delivery. All ten bits must qualify; rejected words still advance the receiver. Shared retained rail/delay drives receiver gain/aperture. Independent peer, +100 ppm initial receiver error; recorded stimulus with 400-bit transition drought. Offline lag is scoreboard-only, not protocol word alignment. No TX electrical model, full protocol traffic, pad actions or BER qualification.')
            if wired_encoded:
                # External observer sees actual host bits, not source indices/lag.
                pattern=pcie_gen1_compliance_bits(1)
                host_bits=[(word>>bit)&1 for word in chip.stream['rx_words'] for bit in range(10)]
                candidates=[i for i in range(max(0,len(host_bits)-79)) if host_bits[i:i+80]==pattern*2]
                first=candidates[0] if candidates else None
                checked=[] if first is None else [host_bits[i:i+40]==pattern for i in range(first,len(host_bits)-39,40)]
                wired_audit['host_pattern_observer']=dict(first_confirmed_pattern_bit=first,
                    checked_blocks=len(checked),mismatched_blocks=sum(not x for x in checked),
                    scope='Two observed compliance-pattern repetitions establish phase; later complete blocks checked without source indices. Repetition cannot detect deletion of whole pattern periods. Not general 8b/10b decode, packet framing or continuous payload proof.')
        turnaround_audit=None
        if tdd_stage:
            before_count=sum(t<origin+1e-6 for t in received_nominal_times)
            after_count=sum(t>=origin+8e-6 for t in received_nominal_times)
            assert before_count and after_count and before_count+after_count==len(received_nominal_times)
            assert chip.epoch==direction_actions[0]['epoch']==direction_actions[1]['epoch']
            assert prefill==0 and sent and all(origin+3e-6<=t<origin+6e-6 for t,_ in sent)
            turnaround_audit=dict(epoch_preserved=True,rx_samples_before=before_count,
                rx_samples_after=after_count,tx_samples=len(sent),synthetic_prefill_bits=prefill,
                first_tx_s=sent[0][0],last_tx_s=sent[-1][0],
                first_resumed_rx_nominal_acquisition_s=next(t for t in received_nominal_times if t>=origin+8e-6),
                scope='Actual data and retained analog state through RX/mute/TX/mute/RX. Explicit RX completion latency; same scheduled sample clock and frame phase. Analog mute is ideal; 2 us settle is assigned, not measured readiness or packet-response latency.')
        rail.advance(chip.time)
        voltage=rf['ledger']['local_payload_clock_core_rail_v']+rail.voltage
        np.testing.assert_allclose(voltage,budget['ledger']['local_payload_clock_core_rail_v'],atol=1e-8)
        old=chip.epoch;state=rail.state.copy();discarded=chip.stop()
        rail.advance(chip.time);np.testing.assert_array_equal(rail.state,state)
        assert chip.epoch>old and chip.stream is None
        try:event(0)
        except ValueError:pass
        else:raise AssertionError('Stopped ownership retained clock callback')
        rows.append(dict(wired_tx_electrical=wired_tx_audit,wired_analog_cdr=wired_audit,reply_execution=reply_execution,turnaround_audit=turnaround_audit,direction_actions=direction_actions,tx_rf_port=tx_port,rf_quality=rf_quality,rf_frontend=(dict(wanted_antenna_dbm=-65.,blocker_antenna_dbm=-50.,
            blocker_offset_hz=12e6,pga_gain_db=configs['rf_rx'].pga_gain_db,rx_cutoff_hz=rx_cutoff,
            filter_state=copy.deepcopy(rx_filter_state),filter_time_s=rx_filter_time,
            scope='Shared antenna loss/noise/nonlinearity and package-driven gain/LO phase feed retained finite-zero filter and SAR. Selected wanted waveform, fixed gain, midpoint forcing at at least 320 MS/s; zero input during inactive intervals with natural filter decay. No packet acquisition, AGC, independent source phase noise or converter-current feedback.') if engine=='rf' and 'rx' in directions else None),host_received_iq=host_iq,analog_armed_s=armed,analog_ready_s=analog_ready_at,tx_conversion=dict(samples=tx_conversions,filter_before_v=[tx_filter_before.real,tx_filter_before.imag],
            filter_after_v=[reconstructed(chip.time).real,reconstructed(chip.time).imag],
            retained_dac_events=len(tx_edges)-1,reference_charge_loading_modeled=False),converter=dict(conversions=len(conversions),
            initial_state=converter_before,final_state=copy.deepcopy(converter_state),
            comparator_model=comparator_model,publication_latency_ceiling_s=sum(parameters.bit_durations_s),
            actual_conversion_latency_interval_s=([min(x['actual_conversion_latency_interval_s'][0] for x in conversions),max(x['actual_conversion_latency_interval_s'][1] for x in conversions)] if conversions else None),
            evaluated_supply_interval_v=([min(x['evaluated_supply_interval_v'][0] for x in conversions),max(x['evaluated_supply_interval_v'][1] for x in conversions)] if conversions else None),
            acquisition_reference_interval_v=([min(x['first_acquisition_reference_v'] for x in conversions),max(x['first_acquisition_reference_v'] for x in conversions)] if conversions else None),
            instantaneous_reference_window_exceedances=sum(x['reference_interval_v'][0]<.98 or x['reference_interval_v'][1]>1.02 for x in conversions),
            decision_reference_interval_v=([min(x['decision_reference_interval_v'][0] for x in conversions),max(x['decision_reference_interval_v'][1] for x in conversions)] if conversions else None),
            code_error_rms_lsb=float(np.sqrt(np.mean([x['code_error_rms_lsb']**2 for x in conversions]))) if conversions else None,
            maximum_absolute_charge_balance_residual_c=max((abs(x['reference_charge_balance_residual_c']) for x in conversions),default=0.),
            reference_charge_drawn_c=sum(x['reference_charge_drawn_c'] for x in conversions)),fault=flow['fault'],recovered_after_fault=stage_index>=5,engine=engine,directions=list(directions),queue_depth_bits=depth,
            verified_tx_payload_bits_after_prefill=tx_payload_bits,verified_rx_payload_bits=rx_payload_bits,epoch=old,start_s=start,end_s=chip.time,
            h2d_word_hz=312.5e6*chip.a.h2d_clock_scale,d2h_word_hz=312.5e6*chip.a.d2h_clock_scale,
            modeled_d2h_capacity_bps=flow['host_capacity_bps'],
            local_current_a=baseline+float(rail.state[4]),load_only_rail_v=voltage,
            inventory_current_ma=budget['inventory_current_report']['total_ma'],
            host_node_current_a=budget['ledger']['host_node_current_a'],
            inventory_mode='rf_tx' if engine=='rf' and directions==('tx',) else 'rf_rx' if engine=='rf' else 'wired',
            incremental_clock_delay_s=rail.clock_delay,
            payload_clock_owner="package-delayed RF RX/TX and wired TX; wired RX independent peer",
            maximum_preview_shift_s=float(max(abs(edges-(nominal-origin)))),
            state_retained_at_stop=True,discarded=discarded))
    usb_extension=None
    if direct_usb:
        from usb_selected_timing import reply_trace,DirectHostState
        usb_config=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=architecture['direct_stream_service']['budget']['host_hz'],
            wired_pad_path='bidirectional')
        context['resolved_configurations']['usb']=usb_config.record()
        usb=b.configured_environment(usb_config)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=usb_config.line_rate_bps))
        chip.a=selected_transport_assumptions(usb)
        chip.configure_transport('direct')
        start=chip.time;before=copy.deepcopy(converter_state)
        rail.ramp_to(start,usb['ledger']['local_branch_current_a']-baseline,100e-9,
            host_increment_a=usb['ledger']['host_node_current_a']-rf['ledger']['host_node_current_a'])
        snapshot()
        pad=chip.wired_pad
        pad.transition_mode('usb',speed='hs',command_delay_s=0.,dead_time_s=3e-9,
                            rail=float(rail_at(np.array([start]))[0]))
        chip.advance(pad.time)
        pad.set_local_passives(termination_ohm=(45.,45.))
        pad.set_peer_passives(termination_ohm=(45.,45.))
        def arm_usb():
            chip.analog_qualification.observe(chip.time,observe_parked_reference(chip.time))
            chip.start();armed=chip.time
            while chip.state=='acquiring':
                time=min(chip.time+100e-9,chip.ready_at)
                chip.advance(time);rail.advance(time)
                chip.analog_qualification.observe(time,observe_parked_reference(time));chip.advance(time)
                if chip.time-armed>100e-6:raise ValueError('USB reference/supply did not qualify')
            return chip.time
        ready=arm_usb()
        chip.wired_pad_supply_step_s=100e-9
        host=DirectHostState(chip)
        exchange=reply_trace(chip=chip,configuration=usb_config,host_state=host,payload=b'A',
                             analog_observer=observe_parked_reference)
        reference_idle_to(chip.time);rail.advance(chip.time)
        fault_exchange_start=chip.time
        reference_targets.extend([(chip.time+300e-9,.8),(chip.time+1.4e-6,reference_target)])
        old_session=chip.direct_session;old_epoch=chip.epoch
        emitted_before=old_session.playback.emitted
        try:
            reply_trace(chip=chip,configuration=usb_config,host_state=host,payload=b'B',analog_observer=observe_parked_reference)
        except AnalogQualificationError:
            if chip.state!='fault':raise
        else:raise AssertionError('Disturbed reference did not stop USB traffic')
        condition_generation+=1
        calibration_fault_events.append(dict(time_s=chip.time,epoch=chip.epoch,
            reason='analog_unqualified',condition_generation=condition_generation))
        fault_time=chip.time;fault_reference=reference_idle_to(fault_time)
        partial_reply_bits=old_session.playback.emitted-emitted_before
        assert 0<partial_reply_bits<48 and pad.local=='Z'
        assert fault_reference<contract['physical_services']['sar_timing']['startup']['model_reference_window_v'][0]
        try:old_session.tick()
        except ValueError:pass
        else:raise AssertionError('Faulted USB session accepted playback')
        chip.wait_faulted(fault_exchange_start+1.5e-6)
        reference_idle_to(chip.time);rail.advance(chip.time)
        fault_discarded=chip.stop();restart=chip.time
        recovered_ready=arm_usb()
        assert recovered_ready-restart>=chip.a.startup_s-1e-15
        try:old_session.tick()
        except ValueError:pass
        else:raise AssertionError('Stale USB epoch accepted playback')
        recovered=reply_trace(chip=chip,configuration=usb_config,host_state=DirectHostState(chip),payload=b'C',
                              analog_observer=observe_parked_reference)
        reference_idle_to(chip.time);rail.advance(chip.time)
        recovery=dict(reference_target_events=reference_targets[1:],fault_time_s=fault_time,
            observed_reference_at_fault_v=fault_reference,partial_reply_bits=partial_reply_bits,
            pad_released_at_fault=True,old_epoch=old_epoch,new_epoch=chip.epoch,
            restart_s=restart,ready_at_s=recovered_ready,discarded=fault_discarded,
            recovered_exchange=recovered,
            scope='Assigned upstream reference-target depression through retained current-limited reference RC, not an injected readiness flag.100ns observations stop a partial reply, release pad and reject old epoch; STOP/rearm uses fresh full guard and same pad/package/reference. Not USB retry semantics, real reference failure dynamics or physical fault latency.')
        final_rail=float(rail_at(np.array([chip.time]))[0])
        np.testing.assert_allclose(final_rail-float(disturbance(chip.time)),
            usb['ledger']['local_payload_clock_core_rail_v'],atol=1e-8,rtol=0.)
        epoch=chip.epoch;discarded=chip.stop()
        usb_extension=dict(start_s=start,ready_at_s=ready,end_s=chip.time,epoch=epoch,
            exchange=exchange,recovery=recovery,converter_initial_state=before,converter_final_state=copy.deepcopy(converter_state),
            inventory_current_ma=usb['inventory_current_report']['total_ma'],
            local_branch_current_a=usb['ledger']['local_branch_current_a'],
            host_node_current_a=usb['ledger']['host_node_current_a'],
            final_supply_v=final_rail,inventory_dc_supply_v=usb['ledger']['local_payload_clock_core_rail_v'],discarded=discarded,
            pad_history='One retained pad, isolated during preceding RF/abstract wired stages; USB explicitly drives and samples it.',
            scope='Same chip, pad, retained converter reservoir and local package trajectory after seven RF/wired stages. USB231.25mA inventory drives a100ns assigned load ramp; preceding RF RX/TX and wired stages use the same architecture inventory. Startup uses fresh reference/supply and existing guard; packet uses100ns observations and physical pad. USB480MHz/100MHz host-follow clocks, input phase and pipelines remain assigned; host-switching harmonics are not recomputed at the USB host rate; no dynamic USB switching-current feedback, mode-change clock qualification, USB protocol retry/recovery or complete coupled-current qualification.')
    tx_checked=[row['tx_rf_port'] for row in rows if row.get('tx_rf_port') and 'requirement_checks' in row['tx_rf_port']]
    tx_summary=dict(evaluated_stages=len(tx_checked),
        all_recorded_requirements_met=all(x['requirements_met'] for x in tx_checked) if tx_checked else None,
        scope='Only recorded power/amplitude/electrical checks; waveform quality is diagnostic and emissions lack a standards mask. Completed lifecycle is not capability acceptance.')
    return dict(context,tx_requirement_summary=tx_summary,usb_extension=usb_extension,diagnostic_sequence=diagnostic_observations,
        calibration_fault_events=calibration_fault_events,final_condition_generation=condition_generation,
        calibration_generation_scope='FPGA-side generation advances once per observed transfer fault and caught USB analog fault in this schedule. Normal STOP/reconfiguration/rearm do not renew records. Normal post-fault RF capture is raw; prior diagnostic data is rejected by the shared validity gate. No serialized fault-poll latency, fitted coefficients or measured calibration requalification.', 
        diagnostic_scope='Stopped zero then +/-VREF/4 then normal selections across existing RF epochs; actual host delivery and retained reference/package. Assigned0.25pF effective reference load per selected quarter-reference lane. No inferred absolute VREF, continuous diagnostic driver model, fitted correction deployment or calibration-validity policy.',shared_supply_stress=stress,wanted_waveform='le_1m_advertising_packet' if packet_rx else 'four_he20_data_symbols' if wideband else 'one_mhz_tone',reference_charge_accounting=reference_accounting(),rf_sample_hz=lo_hz/lo_divider,lo_divider=lo_divider,status='completed_scoped_lifecycle',analog_qualification_events=list(zip(chip.analog_qualification.times,chip.analog_qualification.valid)),
        independent_analog_observations=independent_analog_observations,analog_qualification_max_age_s=qualification_max_age_s,analog_qualification_scope='100 ns model observations during startup; RF RX observations at completed conversions and reference/supply observations at consumed TX words. Independent 100 ns idle observations read retained reference recovery without advancing converter state when enabled. Observation coverage expires at the declared maximum age (default 200 ns); None is an explicit held-observation control. No physical sensing implementation, between-observation voltage bound, filter/gain readiness or complete TX validity monitor.',stages=rows,clock_gap_s=list(fault_gap),fault_epoch=fault_epoch,scope='One BehavioralChip RF RX/RF TX/wired duplex/RF RX/RF TX fault/recovered RF TX/recovered RF RX sequence drives one LocalLoadTransient using one architecture current inventory and both local/HOST load inputs. Assumed warm RF operating point initially; stopped chip retains previous analog load until next configuration. Assigned 100 ns ramp, reference/supply model-observed startup and deterministic bit-checked transport with contract queue depth. Package delay shifts wired TX and RF RX/TX events. Wired RX uses independent peer timing alongside delayed local TX. Default stages STOP and rearm. The explicit turnaround variant retains the first RF stream through RX/TX/RX with assigned settling and ideal mute; no physical fast-TDD qualification follows. TX verification includes data beyond prefill. Preview uses the scheduled load without changing live state and is invalidated by epoch stop. Final RF TX and recovery share a package-delayed divide-by-64 reference-presence monitor with a prescribed 1 us source gap. Actual source-failure dynamics are not modeled. The fault stops payload, STOP discards its queue and invalidates epoch callbacks, and explicit return/rearm restores verified TX data without resetting package state. All stages arm through model-observed reference/supply validity and the existing startup guard. RF RX words now come from retained paired 10-bit SAR conversions of the selected antenna-level wanted waveform plus 12 MHz blocker through the shared noisy nonlinear frontend and retained finite-zero RX filter, packed as two 12-bit transport values. Acquisition completion follows package-delayed sample edges; words enter transport only after the inventory decision latency. The converter reads acquisition, sampling-capacitance, diagnostic-switch loading and cycle guard from the architecture inventory and executes through the chip-owned epoch/configuration binding. Asynchronous paired decisions use the explicit50ps regeneration/100ps launch/200mV threshold hypothesis with actual reference recovery timing. Completed words publish at the inventory decision ceiling; early completion does not advance host events. Physical comparator/sequencer behavior remains unqualified. Reference bias stays enabled with normally 1 V upstream target (the optional USB extension explicitly disturbs it); completed SAR charge/RNG state survives TX/wired/STOP intervals and idle recovery uses retained package history at 1 us midpoint steps. ADC is parked outside RX, with idle state advanced lazily on next conversion. Startup READY now uses 100 ns model-observed reference/supply validity and the existing guard. RF RX completion observations can invalidate payload. No physical sensor or between-observation envelope is inferred. No converter-current feedback into package, physical RF block qualification, host/clock-source noise, or full RF TX port. RF TX words drive the existing native DAC and selected reconstruction at the selected cutoff using actual consumption timestamps, retained held-code history and shared reference idle recovery. Filter state is not reset at STOP or mode change; code holds while RF output is assumed muted. Native DAC transfer is memoryless and its reference loading is not modeled; the shared mixer/driver/load transfer is evaluated, but physical output circuitry, mute waveform, spectral mask and TX current feedback remain unqualified. Not cold-start, analog settling or protocol qualification.')


def turnaround_signal_audit(trace, *, design=None):
    """Known-tone diagnostic of a capture from the supplied shared design."""
    design=load_design() if design is None else design
    if trace.get('design_provenance')!=design.provenance():
        raise ValueError('Turnaround audit requires a capture from the supplied design')
    context=capture_context(design,{'turnaround':trace},operation='turnaround signal audit')
    stage=trace['stages'][0];record=stage['host_received_iq']
    times=np.asarray(record['nominal_sample_times_s'])
    iq=np.asarray(record['signed_iq_words']);z=(iq[:,0]+1j*iq[:,1])/2048
    actions=stage['direction_actions'];before=times<actions[0]['gated_at_s']
    after=times>=actions[1]['ready_at_s'];post=np.flatnonzero(after)
    if before.sum()<16 or len(post)<64:raise ValueError('Insufficient delivered tone record')
    basis=np.exp(2j*np.pi*1e6*times)
    def fit(indices):
        design=np.column_stack((basis[indices],np.ones(len(indices))))
        coeff=np.linalg.lstsq(design,z[indices],rcond=None)[0]
        return coeff
    pre=np.flatnonzero(before);training=post[-64:];coeff=fit(training)
    def score(indices):
        predicted=coeff[0]*basis[indices]+coeff[1]
        return dict(samples=len(indices),first_time_s=float(times[indices[0]]),
            last_time_s=float(times[indices[-1]]),
            normalized_residual_rms=float(np.sqrt(np.mean(abs(z[indices]-predicted)**2))/abs(coeff[0])))
    early=post[:16];held=post[16:-64]
    return dict(**context,training_samples=64,training_is_late_resumed_rx=True,
        pre_switch=score(pre),first_16_resumed=score(early),held_out_resumed=score(held),
        fitted_gain_ratio_after_to_before=float(abs(coeff[0])/abs(fit(pre)[0])),
        resumed_delivered_samples=len(post),
        scope='Retrospective known 1 MHz tone fit on final 64 resumed host samples; common fitted gain/DC used for all scored windows. Not causal packet acquisition, protocol EVM, readiness proof or hidden analog timestamp correction. Exposes transient errors despite correct payload transport.')


def tx_local_supply_requirement(contract, trace, *, design=None, primitive_reason=None):
    """Inverse local-rail requirement for a frozen, already observed TX waveform."""
    if primitive_reason is not None:
        if not isinstance(primitive_reason,str) or not primitive_reason.strip():
            raise ValueError('Independent TX supply fixture requires a reason')
        if design is not None or trace.get('design_provenance') is not None:
            raise ValueError('Design-bound TX supply audit cannot be labeled a primitive fixture')
        context=dict(model_role='independent_mathematical_fixture',primitive_reason=primitive_reason)
    else:
        design=b.design_for_contract(contract,design)
        if trace.get('design_provenance') != design.provenance():
            raise ValueError('TX supply audit requires a capture from the supplied design; regenerate missing or mismatched provenance')
        context=capture_context(design,{'tx':trace},operation='TX supply audit')
        context['model_role']='frozen_waveform_inverse_requirement'
    port=trace['stages'][1]['tx_rf_port']
    rail=port['electrical']['minimum_supply_v']
    power=port['data_interval_power']['mean_load_power_w']
    goal=1e-3*10**(contract['generic_configuration_target']['tx_port_power_goal']['mean_load_power_dbm']/10)
    # Under the existing linear rail-to-output gain law, P scales as V**2.
    minimum=rail*np.sqrt(goal/power)
    cases=[]
    for ripple in (0.,.0096,.06):
        cases.append(dict(local_peak_ripple_v=ripple,
            sufficient_local_dc_floor_v=float(minimum+ripple),
            recorded_dc_meets_floor=bool(rail>=minimum+ripple),
            dc_shortfall_v=float(max(0.,minimum+ripple-rail))))
    return dict(**context,recorded_nominal_gain=port['nominal_gain_requirement'],
        recorded_local_rail_v=rail,recorded_mean_power_w=power,
        minimum_instantaneous_rail_for_frozen_waveform_v=float(minimum),cases=cases,
        scope='Inverse gain-law screen only: hold converter/reference/reconstruction, phase, distortion and waveform fixed. Requiring the instantaneous rail above this floor is sufficient for mean power under that restricted law, not necessary for AC ripple. Do not infer actual ripple-modulated power/EVM, regulator attenuation, or physical gain independence. Board voltage must additionally cover feed drop and tolerances; no ideal local regulator is inserted.',
        decision='Use as a local-rail requirement for the common network, not a prescribed board voltage. Rerun the retained conversion chain at the resulting rail before accepting the power goal.')


def tx_power_goal_audit(contract, trace, *, design=None):
    """Inverse requirements at recorded crest factor; no new waveform claim."""
    from selected_rf import tx_power_requirement,tx_amplitude_bound
    design=b.design_for_contract(contract,design)
    if trace.get('design_provenance') != design.provenance():
        raise ValueError('TX power audit requires a capture from the supplied design; regenerate missing or mismatched provenance')
    requirement=contract['generic_configuration_target']['tx_amplitude_operating_requirement']
    goal=contract['generic_configuration_target']['tx_port_power_goal']['mean_load_power_dbm']
    recorded=trace['stages'][1]['tx_rf_port']
    measured=recorded['data_interval_power']
    amplitude=recorded['amplitude_requirement']
    if not all(key in amplitude for key in ('driver_parameters','output_parameters')):
        raise ValueError('TX power audit requires recorded driver and output parameters; regenerate legacy evidence')
    driver=amplitude['driver_parameters'];output=amplitude['output_parameters']
    nominal_gain=recorded['nominal_gain_requirement']
    source_r=driver['source_r_ohm_differential'];load_r=driver['load_ohm_differential']
    resistance=source_r+load_r;headroom=2*driver['headroom_per_rail_v']
    current_limit=driver['bias_current_a']*resistance
    bound=tx_amplitude_bound(requirement,nominal_gain=nominal_gain,
        gain_reference_v=driver['gain_reference_v'],driver_parameters=driver,output_parameters=output,reconstruction_family=lifecycle_tx_filter(design)[0])
    # Ignoring compression makes this an optimistic upper bound on voltage.
    mixer_peak=bound['iq_operator_gain_bound']*requirement['reconstructed_complex_peak_v']+abs(output['lo_feedthrough'])
    crest=10**(measured['peak_to_mean_load_power_db']/10)
    rows=[]
    for rail in (requirement['supply_interval_v'][0],3.3,requirement['supply_interval_v'][1]):
        port=tx_power_requirement(mean_load_power_w=1e-3*10**(goal/10),
            crest_factor_db=measured['peak_to_mean_load_power_db'],minimum_supply_v=rail,source_resistance_ohm=source_r,load_resistance_ohm=load_r,
            peak_current_limit_a=driver['bias_current_a'],headroom_per_rail_v=driver['headroom_per_rail_v'])
        gain=nominal_gain*rail/driver['gain_reference_v']
        available=min(gain*mixer_peak,rail-headroom,current_limit)
        ceiling=(available/resistance)**2*load_r/(2*crest)
        rows.append(dict(rail_v=rail,necessary_port_bound=port,
            optimistic_amplitude_limited_mean_power_dbm=float(10*np.log10(ceiling/1e-3)),
            actual_model_gain=gain,
            required_gain_ignoring_compression=port['required_open_peak_v']/mixer_peak,
            necessary_amplitude_bound_pass=ceiling>=1e-3*10**(goal/10)))
    # Necessary power lower bound versus sufficient all-amplitude headroom bound.
    # The interval is a screening window, not proof any waveform achieves it.
    gain_lower=max(row['required_gain_ignoring_compression']*driver['gain_reference_v']/row['rail_v'] for row in rows)
    gain_upper=min(min(v-headroom,current_limit)*driver['gain_reference_v']/(v*mixer_peak)
                   for v in requirement['supply_interval_v'])
    gain_window=dict(nominal_gain_lower_necessary=gain_lower,
        nominal_gain_upper_sufficient_headroom=gain_upper,
        screening_interval_nonempty=gain_lower<=gain_upper,
        optimistic_power_margin_db=float(20*np.log10(gain_upper/gain_lower)),
        scope='Fixed nominal gain across the declared rail interval, fixed recorded crest factor and full reconstructed amplitude allowance. Lower bound ignores compression and uses an upper bound on mixer amplitude; upper bound guarantees headroom under the same amplitude contract. A nonempty interval is not waveform feasibility; an empty interval would reject this sufficient amplitude policy, not all possible waveforms. No new gain setting selected.')
    return dict(**capture_context(design,{'tx':trace},operation='TX power audit'),source_design_provenance=trace.get('design_provenance'),recorded_driver_parameters=driver,recorded_output_parameters=output,fixed_gain_screen=gain_window,goal_dbm=goal,recorded_crest_factor_db=measured['peak_to_mean_load_power_db'],cases=rows,
        candidate_gain_amplitude_bounds={str(g):tx_amplitude_bound(requirement,nominal_gain=g,gain_reference_v=driver['gain_reference_v'],driver_parameters=driver,output_parameters=output,reconstruction_family=lifecycle_tx_filter(design)[0]) for g in (4.5,5.36)},
        decision='Port-only headroom is insufficient. Keep physical driver provisionally; change/qualify amplitude or gain policy, or a lower-crest waveform, before claiming the goal at nominal/minimum supply.',
        scope='Necessary bounds at a fixed recorded output crest factor, not a rescaled waveform simulation. Compression only lowers the optimistic amplitude bound in the declared monotonic range. A new waveform or gain must recheck crest factor, distortion, emissions and complete retained-history amplitude. No extra analog gain, power or PA selected.')


def analog_operating_summary(report, *, design=None):
    """Observed cross-schedule ranges; never a continuous uncertainty bound."""
    design=load_design() if design is None else design
    captures={name:report[name] for name in ('joined_tx_operating_envelope','joined_wired_recovery')}
    for name,trace in captures.items():
        if trace.get('design_provenance')!=design.provenance():
            raise ValueError(name+' summary requires a capture from the supplied design')
    context=capture_context(design,captures,operation='analog operating summary')
    groups=[]
    for name in ('joined_tx_operating_envelope','joined_wired_recovery'):
        trace=report[name];rx=[];tx=[]
        for index,stage in enumerate(trace['stages']):
            quality=stage.get('rf_quality')
            if quality:
                rx.append(dict(stage=index,evm_rms=quality['evm_rms'],
                    errors=quality['bpsk_errors'],evaluated_bits=quality['evaluated_bits'],
                    real_preamble_acquisition=quality['real_preamble_acquisition']))
            port=stage.get('tx_rf_port') or {}
            if 'data_interval_power' in port:
                tx.append(dict(stage=index,mean_load_power_dbm=port['data_interval_power']['mean_load_power_dbm'],
                    evm_rms=port['quality']['evm_rms'],
                    gain=port['nominal_gain_requirement'],
                    native_peak_code=port['host_preparation']['native_complex_code_peak']))
        if not rx or not tx:raise ValueError('Complete observed RX and TX records required')
        groups.append(dict(source=name,source_trace_sha256=hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest(),
            recorded_sources_sha256=trace['sources_sha256'],stress=trace['shared_supply_stress'],rx=rx,tx=tx))
    first=groups[0]['stress']
    for group in groups[1:]:
        for field in ('source_offset_v','ripple_peak_v','ripple_hz','delay_sensitivity_multiplier'):
            if group['stress'][field]!=first[field]:raise ValueError('Cannot pool different imposed envelopes')
    rx=[r for g in groups for r in g['rx']];tx=[r for g in groups for r in g['tx']]
    return dict(**context,cases=groups,
        observed_rx_evm_interval=[min(r['evm_rms'] for r in rx),max(r['evm_rms'] for r in rx)],
        observed_tx_evm_interval=[min(r['evm_rms'] for r in tx),max(r['evm_rms'] for r in tx)],
        observed_tx_power_dbm_interval=[min(r['mean_load_power_dbm'] for r in tx),max(r['mean_load_power_dbm'] for r in tx)],
        worst_rx_case=max((dict(source=g['source'],**r) for g in groups for r in g['rx']),key=lambda r:r['evm_rms']),
        next_decision='Establish RF quality acceptance and a justified shared local-rail envelope, including phase/arrival/history variation; do not choose a supply from a single favorable schedule.',
        scope='Union of recorded finite DATA observations with matching imposed stress, retaining source revisions and schedules. Not a matched controlled phase experiment, continuous bound, PER/BER confidence, standards acceptance, cold-start proof or physically produced rail envelope. Short error-free records do not promote capabilities; zero and adverse ripple controls remain separate evidence.')


def monitor_recovery_environment(design, mode):
    """Configuration for the command's synthetic payload/clock-loss exercise."""
    if mode=='rf':
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=256,pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    elif mode=='wire':
        config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
    else:raise ValueError('Unknown monitor-recovery engine')
    scenario=Scenario()
    return b.configured_environment(config,scenario),dict(design_provenance=design.provenance(),
        resolved_configuration=config.record(),scenario_overrides=scenario.record(),
        probe_assumptions=dict(payload='Deterministic index*73+19 words',
            clock_gap_s=[design.contract['physical_services']['sar_timing']['startup']['assigned_guard_s']+offset for offset in (2e-6,3e-6)],monitor_divider=64,
            rf_filter_hz=dict(rx=1e6,tx=3e6),
            wired_rx_clock='Independent uniform peer fixture; TX uses delivered clock'))


def monitor_recovery_campaign(design):
    """Synthetic payload recovery using one shared design and startup-relative gaps."""
    rows=[]
    for mode in ('wire','rf'):
        raw,context=monitor_recovery_environment(design,mode)
        resolved=raw['resolved_configuration']
        carrier=resolved['reference_hz']
        environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
        assert environment is not None
        startup=environment['transport_parameters']['startup_s']
        gap_start,gap_end=context['probe_assumptions']['clock_gap_s']
        horizon=gap_end+startup+20e-6
        # Every 64th edge represents an assigned monitor prescaler, not a new pin.
        ideal=np.arange(1,int(horizon*carrier/64)+1)*64/carrier
        edges=ideal+DeliveredClock(environment).crossing_error(ideal,carrier)
        edges=edges[(edges<gap_start)|(edges>=gap_end)]
        chip=BehavioralChip(selected_transport_assumptions(environment))
        if mode=='wire':chip.configure_numeric(engine=mode,timing=dict(line_rate_bps=carrier))
        else:chip.configure_numeric(engine=mode,rf=dict(sample_hz=resolved['sample_hz'],sample_clock_source="external_lo",lo_hz=carrier,lo_divider=resolved['sample_divider'],**lifecycle_filter_settings(design,1e6,3e6)))
        chip.attach_reference(edges,timeout_s=100e-9,monitor_tick_s=10e-9,required_edges=4)
        chip.start();chip.advance(chip.ready_at+1e-6);assert chip.state=='active'
        sample_bits=10 if mode=='wire' else 24
        sample_hz=resolved['line_rate_bps']/10 if mode=='wire' else resolved['sample_hz']
        emitted=[]
        def source(index):
            value=(index*73+19)&((1<<sample_bits)-1);emitted.append(value);return value
        depth=design.contract['transport']['scheduling']['ingress_bits_per_source']
        transfer=dict(mode=1,source_hz=sample_hz,sample_bits=sample_bits,frames=16,depth_bits=depth,
                      directions=('rx',),rx_source=chip.bind_stream_callback(source))
        def bind_rx_events():
            if mode!='rf':return
            origin=chip.time
            nominal=origin+np.arange(1,1001)/sample_hz
            absolute=nominal+DeliveredClock(environment).crossing_error(nominal,carrier)
            absolute=absolute[(absolute<gap_start)|(absolute>=gap_end)]
            transfer['rx_event_time']=chip.bind_stream_callback(lambda index:float(absolute[index]-origin))
            return absolute
        rx_events=bind_rx_events()
        flow=chip.transfer(epoch=chip.epoch,**transfer)
        assert flow['fault']=='reference_lost'
        delivered=list(chip.stream['rx_words'])
        if mode=='rf':assert all(not gap_start<=t<gap_end for t in rx_events[:len(emitted)])
        def check_payload(words,source_words):
            actual=[(word>>bit)&1 for word in words for bit in range(10)]
            expected=[(word>>bit)&1 for word in source_words for bit in range(sample_bits)]
            assert actual and actual==expected[:len(actual)]
        check_payload(delivered,emitted)
        fault_time=chip.time;assert gap_start<=fault_time<=gap_start+110e-9 and chip.state=='fault'
        old_callbacks=[transfer[k] for k in ('rx_source','rx_event_time') if k in transfer]
        old_epoch=chip.epoch;discarded=chip.stop();assert chip.epoch>old_epoch
        chip.advance(gap_end+100e-9);chip.start();chip.advance(chip.ready_at)
        assert chip.state=='active'
        recovered_at=chip.time
        try:chip.transfer(epoch=old_epoch,**transfer)
        except ValueError:pass
        else:raise AssertionError('Stale epoch accepted after recovery')
        before=len(emitted)
        for callback in old_callbacks:
            try:callback(0)
            except ValueError:pass
            else:raise AssertionError('Pre-fault callback accepted after restart')
        assert len(emitted)==before
        emitted.clear()
        transfer['rx_source']=chip.bind_stream_callback(source)
        bind_rx_events()
        recovered=chip.transfer(epoch=chip.epoch,**transfer)
        assert recovered['fault'] is None
        recovered_words=list(chip.stream['rx_words']);check_payload(recovered_words,emitted)
        tx_lifecycle=wired_tx_lifecycle(environment,edges,loss_window_s=(gap_start,gap_end)) if mode=='wire' else None
        rows.append(dict(context,rx_clock_owner="external_lo_divided" if mode=="rf" else "independent_peer_uniform_fixture",wired_tx_lifecycle=tx_lifecycle,delivered_words_before_fault=len(delivered),
            delivered_words_after_recovery=len(recovered_words),payload_prefix_correct=True,
            stale_epoch_rejected=True,stale_callbacks_rejected=len(old_callbacks),discarded=discarded,engine=mode,carrier_hz=carrier,monitor_divider=64,
            startup_guard_s=startup,queue_depth_bits=depth,injected_clock_gap_s=[gap_start,gap_end],fault_time_s=fault_time,recovered_at_s=recovered_at,
            epoch_before_fault=old_epoch,epoch_after_stop=chip.epoch,clock_status=clock['status'],
            clock_current_a=environment['ledger']['total_chip_supply_current_a'],
            h2d_word_hz=312.5e6*chip.a.h2d_clock_scale,d2h_word_hz=312.5e6*chip.a.d2h_clock_scale))
    return rows


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wired-peer-controls',action='store_true',help='Existing USB electrical lifecycle with independent peer terminations')
    parser.add_argument('--ownership-turnaround',action='store_true',help='Retained RX/TX/RX within the first RF stage without STOP')
    parser.add_argument('--stress-ripple-hz',type=float,default=10e6,help='Assigned common ripple frequency; requires --ownership-stress for nondefault values')
    parser.add_argument('--ownership-wired-electrical',action='store_true',help='Actual wired TX words through loaded channel/independent peer alongside selected RX')
    parser.add_argument('--ownership-wired-equalized',action='store_true',help='Join the already-selected CTLE with encoded wired RX')
    parser.add_argument('--wired-noise-attribution',action='store_true',help='Matched detector/voltage-noise diagnostic with unchanged CDR threshold')
    parser.add_argument('--ownership-wired-fail-closed',action='store_true',help='Latch existing stream fault on loss after wired RX acquisition')
    parser.add_argument('--ownership-wired-encoded',action='store_true',help='Joined CDR with existing PCIe compliance-pattern stimulus')
    parser.add_argument('--ownership-wired-cdr',action='store_true',help='Loaded wired RX/CDR drives selected lifecycle host delivery')
    parser.add_argument('--ownership-reply',action='store_true',help='Execute first approved scan response through retained chip TX')
    parser.add_argument('--ownership-request',action='store_true',help='Joined addressed scan request with causal response-service budget')
    parser.add_argument('--ownership-packet',action='store_true',help='Real LE 1M packet through retained RX lifecycle and actual host delivery')
    parser.add_argument('--turnaround-signal',action='store_true',help='Signal continuity audit of recorded retained-clock turnaround')
    parser.add_argument('--ownership-tx-gain',action='store_true',help='Candidate 5.36 nominal gain at 180-code target; no cost or physical gain qualification')
    parser.add_argument('--ownership-tx-range',action='store_true',help='Joined wideband case at 180 native peak codes, existing analog gain')
    parser.add_argument('--tx-power-requirement',action='store_true',help='Inverse port and full-amplitude TX power requirements')
    parser.add_argument('--turnaround-requirement',action='store_true',help='Selected end-to-end same-channel response allowance')
    parser.add_argument('--analog-envelope-summary',action='store_true',help='Consolidate observed analog ranges across recorded joined schedules without simulation')
    parser.add_argument('--joint-wired-recovery',action='store_true',help='Retained RF/wired/RF lifecycle with live wired fault publication and rearm')
    parser.add_argument('--wired-recovery',action='store_true',help='Loaded continuous-peer recovery with shared disturbance and sticky host fault polling')
    parser.add_argument('--joint-tx-envelope',action='store_true',help='Join high-amplitude TX candidate with the existing reduced-ripple RF/wired envelope')
    parser.add_argument('--ripple-envelope',action='store_true',help='Matched whole-path ripple requirements at fixed source offset and sensitivity')
    parser.add_argument('--supply-requirement',action='store_true',help='Fast inverse blocker requirement from the recorded shared stress')
    parser.add_argument('--ownership-stress',action='store_true',help='Joined wideband lifecycle under one explicit simultaneous supply/timing stress')
    parser.add_argument('--ownership-wideband',action='store_true',help='Same retained lifecycle with four HE20 DATA symbols per RX stage')
    parser.add_argument('--ownership-diagnostics',action='store_true',help='Join stopped ADC diagnostic selections and reference load to RF/wired/USB lifecycle')
    parser.add_argument('--ownership-usb',action='store_true',help='Append direct USB to retained RF/wired lifecycle with live analog qualification')
    parser.add_argument('--ownership',action='store_true',help='Fast four-path ownership/data-continuity sequence only')
    parser.add_argument('--causal-recharge',action='store_true',help='Retained SAR retune and clock-loss continuation with causal package-current propagation')
    args=parser.parse_args()
    if args.ownership_tx_gain:args.ownership_tx_range=True
    if args.ownership_wired_electrical:args.ownership_wired_equalized=True
    if args.ownership_wired_equalized:args.ownership_wired_encoded=True
    if args.ownership_wired_fail_closed:args.ownership_wired_encoded=True
    if args.ownership_wired_encoded:args.ownership_wired_cdr=True
    if args.ownership_reply:args.ownership_request=True
    if args.ownership_request:args.ownership_packet=True
    if args.stress_ripple_hz!=10e6 and not args.ownership_stress:parser.error("Nondefault ripple requires --ownership-stress")
    p=b.P;design=load_design();c=design.contract;rows=[]
    if args.causal_recharge:
        hashes=b.baseline_source_hashes()
        base={};package=full_package_handover(c,adc_current_a=None,rf_retune=True,capture=base,design=design)
        capture={}
        retune=retained_sar_retune(c,package_capture=(package,base),extend_until_s=22e-6,capture_out=capture,design=design)
        fault={}
        package_clock_loss(c,base,loss_at_s=retune['converter_stages'][-1]['final_state']['end_time_s']+2e-9,capture_out=fault,design=design)
        continuation=clock_loss_sar_continuation(c,base,fault,retune,capture,design=design)
        if b.baseline_source_hashes()!=hashes:raise RuntimeError('Sources changed during recharge campaign')
        path=p/'evidence/selected-lifecycle.json'
        report=json.loads(path.read_text()) if path.exists() else {}
        report['causal_reference_continuation']=dict(retune=retune,continuation=continuation,sources_sha256=hashes,
            scope='Selected package and retained SAR retune followed by source loss/return. Fixed-duration SAR decisions; this does not qualify slower asynchronous comparator timing or full protocol recovery.')
        b.write_evidence(path,report)
        print(json.dumps(dict(retune_converged=retune['numerical_feedback_converged'],continuation_converged=continuation['numerical_feedback_converged'])))
        return

    if args.wired_peer_controls:
        from behavioral import usb_pad_lifecycle,usb_observed_response
        hashes=b.baseline_source_hashes()
        packets=[dict(peer_termination_ohm=r,result=usb_observed_response(
            request_lengths=(64,),clock_phases=((0.,0.),),usb_data_packet=True,peer_termination_ohm=r,
            playback_capacity_bits=c['transport']['scheduling']['ingress_bits_per_source']))
            for r in (45.,15000.)]
        result=dict(cases=usb_pad_lifecycle(),packet_transport_controls=packets,
            selected_playback_allocation_bits=c['transport']['scheduling']['ingress_bits_per_source'],
            transport_identity='TimedRecordReturn/TimedRecordPlayback and bit_event_codec; separate from canonical BehavioralChip transport. Matching allocation does not establish architectural equivalence.',sources_sha256=hashes,
            scope='Existing standalone electrical lifecycle migrated to explicit peer passive controls; not joined package/host/command or complete USB negotiation.')
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during wired control computation')
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        report['independent_usb_pad_lifecycle']=result;b.write_evidence(path,report);return
    if args.analog_envelope_summary:
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        result=analog_operating_summary(report,design=design)
        result['summary_implementation_sha256']=hashlib.sha256((p/'verification/selected_lifecycle.py').read_bytes()).hexdigest()
        report['analog_operating_summary']=result;b.write_evidence(path,report)
        print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));return
    if args.joint_wired_recovery:
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        hashes=b.baseline_source_hashes()
        result=ownership_load_trace(c,wideband=True,shared_stress=True,
            stress_ripple_peak_v=.0096,tx_native_peak=180.,tx_nominal_gain=5.36,wired_recovery=True,design=design)
        assert result['status']=='completed_scoped_lifecycle' and len(result['stages'])==7
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle envelope computation')
        result['sources_sha256']=hashes
        report=json.loads(path.read_text());report['joined_wired_recovery']=result
        b.write_evidence(path,report);return
    if args.wired_recovery:
        hashes=b.baseline_source_hashes()
        result=loaded_wired_recovery(c,design=design)
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during wired recovery computation')
        result['sources_sha256']=hashes
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        report['loaded_wired_recovery']=result;b.write_evidence(path,report)
        print(json.dumps(result,indent=2));return
    if args.joint_tx_envelope:
        path=p/'evidence/selected-lifecycle.json'
        hashes=b.baseline_source_hashes()
        trace=ownership_load_trace(c,wideband=True,shared_stress=True,
            stress_ripple_peak_v=.0096,tx_native_peak=180.,tx_nominal_gain=5.36,
            wired_cdr=True,wired_encoded=True,wired_equalized=True,wired_tx_electrical=True,
            wired_fail_closed=args.ownership_wired_fail_closed,design=design)
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle envelope computation')
        trace['sources_sha256']=hashes
        trace['fault_policy']='stop_on_rx_qualification_loss' if args.ownership_wired_fail_closed else 'diagnostic_continue_across_rx_loss'
        if args.ownership_wired_fail_closed:
            assert trace['status']=='rejected_by_rx_qualification'
            assert trace['failed_stage']['index']==2
        trace['comparison_scope']='Previously separate 180-code/5.36-gain TX and reduced-ripple shared envelope now run together. Assigned -33 mV source offset, 9.6 mV peak at 10 MHz, fourfold delay sensitivity. No new regulator, rail uplift, resource credit or physical qualification.'
        report=json.loads(path.read_text());report['joined_tx_fail_closed' if args.ownership_wired_fail_closed else 'joined_tx_operating_envelope']=trace
        b.write_evidence(path,report)
        print(json.dumps([dict(engine=r['engine'],rf_quality=r['rf_quality'],
            tx_power=r['tx_rf_port'].get('data_interval_power') if r['tx_rf_port'] else None)
            for r in trace['stages']],indent=2));return
    if args.ripple_envelope:
        hashes=b.baseline_source_hashes()
        cases=[]
        for amplitude in (0.,.0096,.060):
            trace=ownership_load_trace(c,wideband=True,shared_stress=True,
                stress_ripple_peak_v=amplitude,wired_cdr=True,wired_encoded=True,
                wired_equalized=True,wired_tx_electrical=True,design=design)
            cases.append(dict(stress=trace['shared_supply_stress'],status=trace['status'],
                stages=[{key:stage[key] for key in ('engine','directions','fault',
                    'rf_quality','tx_rf_port','wired_analog_cdr','wired_tx_electrical')}
                    for stage in trace['stages']]))
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle envelope computation')
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        report['joined_ripple_envelope']=dict(cases=cases,sources_sha256=hashes,
            scope='Matched seven-stage wideband RF and selected wired RX/TX at 0/9.6/60 mV peak 10 MHz ripple, fixed -33 mV source offset and 4x delay sensitivity. Requirements probe, not measured attenuation, continuous envelope, RF packet/emissions qualification or selected supply circuit.')
        b.write_evidence(path,report);return
    if args.wired_noise_attribution:
        hashes=b.baseline_source_hashes()
        cases=[]
        for control in ('nominal', 'detector_off', 'voltage_off', 'both_off', 'detector_half', 'voltage_half'):
            trace=ownership_load_trace(c,wired_cdr=True,wired_encoded=True,wired_noise_control=control,design=design)
            cases.append(dict(control=control,status=trace['status'],wired=trace['stages'][2]['wired_analog_cdr']))
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during wired control computation')
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        report['wired_noise_attribution']=dict(cases=cases,sources_sha256=hashes,scope='Same joined lifecycle, encoded stimulus, pad/driver, initial phase/ppm, seed and 0.1 UI/64-edge criterion. Remove assigned 5 ps detector noise and/or 10 mV RMS deterministic receiver disturbance, then separately halve either contribution; retain DC offset and shared rail/aperture. Diagnostic attribution, not proposed zero-noise silicon or qualification.')
        b.write_evidence(path,report);print(json.dumps(cases,indent=2));return
    if args.turnaround_signal:
        hashes=b.baseline_source_hashes()
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        trace=report['ownership_turnaround_trace'];result=turnaround_signal_audit(trace,design=design)
        result['source_trace_sha256']=hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during turnaround signal audit')
        result['sources_sha256']=hashes
        report['turnaround_signal_audit']=result;b.write_evidence(path,report);print(json.dumps(result,indent=2));return
    if args.tx_power_requirement:
        hashes=b.baseline_source_hashes()
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        trace=report['ownership_wideband_trace']
        result=tx_power_goal_audit(c,trace,design=design)
        candidate=report['ownership_tx_gain_candidate']
        result['candidate_local_supply_requirement']=tx_local_supply_requirement(c,candidate,design=design)
        result['candidate_trace_sha256']=hashlib.sha256(json.dumps(candidate,sort_keys=True).encode()).hexdigest()
        result['source_trace_sha256']=hashlib.sha256(json.dumps(trace,sort_keys=True).encode()).hexdigest()
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle requirement computation')
        result['sources_sha256']=hashes
        report['tx_port_power_requirement']=result;b.write_evidence(path,report);print(json.dumps(result,indent=2));return
    if args.turnaround_requirement:
        hashes=b.baseline_source_hashes()
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        result=selected_turnaround_requirement(c,design=design)
        result['runtime_control_audit']=selected_direction_control_audit(c,design=design)
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle requirement computation')
        result['sources_sha256']=hashes
        report['selected_turnaround_requirement']=result;b.write_evidence(path,report);return
    if args.supply_requirement:
        hashes=b.baseline_source_hashes()
        from selected_rf import supply_blocker_requirement,passive_supply_isolation_requirement
        path=p/'evidence/selected-lifecycle.json';report=json.loads(path.read_text())
        stress_trace=report['ownership_stress_trace'];stress=stress_trace['shared_supply_stress']
        inputs=dict(carrier_hz=2.4e9,ripple_hz=stress['ripple_hz'],ripple_peak_v=stress['ripple_peak_v'],
            mean_rail_v=stress_trace['stages'][0]['load_only_rail_v']+stress['source_offset_v'],
            sensitivity_s_per_v=c['physical_services']['external_clock_input']['supply_sensitivity_ps_per_mv']*1e-9*stress['delay_sensitivity_multiplier'],
            delay_pole_hz=c['physical_services']['external_clock_input']['supply_delay_pole_hz'],blocker_over_wanted_db=15.)
        result=supply_blocker_requirement(**inputs);result['inputs']=inputs
        from selected_revision_check import owner_current_gate
        ownership=owner_current_gate(c)['selected_planning_case']
        currents=ownership['rail_current_a']
        result['passive_isolation_budget']={
            'assumptions':'Favorable whole 500 pF reservoir given to each candidate separately, not simultaneously. Input minimum 3.3 V minus 1%; load floor 2.5 V is the converter model floor, not a qualified clock minimum.',
            'cases':{name:passive_supply_isolation_requirement(
                frequency_hz=inputs['ripple_hz'],input_ripple_v=inputs['ripple_peak_v'],
                output_ripple_v=result['conservative_combined_small_signal_ripple_limit_v'],
                load_current_a=currents[name],capacitance_f=500e-12,
                input_min_v=3.3*.99,load_min_v=2.5) for name in ('rf','pll')},
            'decision':'Do not select a series-R/on-die-C filter for the entire RF or timing load under this allocation. External supply/return improvements or an explicitly budgeted active solution remain candidates.'}

        result['stress_section_sha256']=hashlib.sha256(json.dumps(stress_trace,sort_keys=True).encode()).hexdigest()
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle requirement computation')
        result['sources_sha256']=hashes
        report['shared_stress_inverse_requirement']=result;b.write_evidence(path,report);return
    if args.ownership or args.ownership_diagnostics or args.ownership_usb or args.ownership_wideband or args.ownership_stress or args.ownership_turnaround or args.ownership_tx_range or args.ownership_packet or args.ownership_wired_cdr:
        hashes=b.baseline_source_hashes()
        result=ownership_load_trace(c,diagnostic_sequence=args.ownership_diagnostics,direct_usb=args.ownership_usb or args.ownership_diagnostics,tx_nominal_gain=5.36 if args.ownership_tx_gain else 4.5,wired_tx_electrical=args.ownership_wired_electrical,wired_equalized=args.ownership_wired_equalized,wired_fail_closed=args.ownership_wired_fail_closed,wired_encoded=args.ownership_wired_encoded,wired_cdr=args.ownership_wired_cdr,packet_reply=args.ownership_reply,packet_request=args.ownership_request,stress_ripple_hz=args.stress_ripple_hz,packet_rx=args.ownership_packet,lo_divider=256 if args.ownership_packet else 64,wideband=(args.ownership_wideband or args.ownership_stress or args.ownership_tx_range) and not args.ownership_packet,tx_native_peak=180. if args.ownership_tx_range else 50.,shared_stress=args.ownership_stress,turnaround=args.ownership_turnaround,design=design)
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during lifecycle ownership computation')
        result['sources_sha256']=hashes
        path=p/'evidence/selected-lifecycle.json'
        report=json.loads(path.read_text()) if path.exists() else {}
        report['ownership_diagnostic_trace' if args.ownership_diagnostics else 'ownership_usb_trace' if args.ownership_usb else 'ownership_tx_gain_candidate' if args.ownership_tx_gain else 'ownership_wired_electrical_stress_trace' if args.ownership_wired_electrical and args.ownership_stress else 'ownership_wired_electrical_trace' if args.ownership_wired_electrical else 'ownership_wired_equalized_fail_closed_trace' if args.ownership_wired_equalized and args.ownership_wired_fail_closed else 'ownership_wired_equalized_trace' if args.ownership_wired_equalized else 'ownership_wired_fail_closed_trace' if args.ownership_wired_fail_closed else 'ownership_wired_encoded_trace' if args.ownership_wired_encoded else 'ownership_wired_cdr_trace' if args.ownership_wired_cdr else 'ownership_reply_trace' if args.ownership_reply else 'ownership_request_trace' if args.ownership_request else 'ownership_packet_stress_frequency_trace' if args.ownership_packet and args.ownership_stress and args.stress_ripple_hz!=10e6 else 'ownership_stress_frequency_trace' if args.ownership_stress and args.stress_ripple_hz!=10e6 else 'ownership_packet_stress_trace' if args.ownership_packet and args.ownership_stress else 'ownership_packet_trace' if args.ownership_packet else 'ownership_tx_range_trace' if args.ownership_tx_range else 'ownership_turnaround_trace' if args.ownership_turnaround else 'ownership_stress_trace' if args.ownership_stress else 'ownership_wideband_trace' if args.ownership_wideband else 'ownership_load_trace']=result
        b.write_evidence(path,report)
        return
    hashes=b.baseline_source_hashes()
    rows=monitor_recovery_campaign(design)
    if b.baseline_source_hashes()!=hashes:
        raise RuntimeError('Sources changed during lifecycle campaign')
    from reference_input_probe import check_network,check_package_transient,check_package_continuation
    validation=check_network();validation['transient']=check_package_transient()
    validation['periodic_continuation']=check_package_continuation()
    retune,refinement=retained_sar_refinement(c,design=design)
    restart_capture={}
    restart=full_package_handover(c,adc_current_a=None,reverse=True,capture=restart_capture,design=design)
    filter_startup=filter_startup_screen(c)
    requirement=next(row for row in filter_startup['cases'] if row['cutoff_hz']==1e6)
    filter_qualification=dict(requirement,enabled_at_s=.4e-6,
        valid_at_s=.4e-6+requirement['settling_s'],
        scope='Conditional bounded-input-history certificate at the existing 1 MHz RX setting. This qualifies a residual-error budget, not simulated RF-filter internal nodes or bias. The SAR still receives the known baseband test tone; omitted history error is bounded rather than injected. No unknown-charge or changed-coefficient qualification.')
    restart_end=filter_qualification['valid_at_s']+c['physical_services']['sar_timing']['startup']['assigned_guard_s']+2e-6
    conversion_capture={}
    joined_restart=retained_sar_retune(c,feedback_grid_s=.0625e-9,package_capture=(restart,restart_capture),extend_until_s=restart_end,capture_out=conversion_capture,design=design)
    joined_restart['transport']=extended_sar_transport(c,joined_restart,qualification_trace=conversion_capture['trace'],d2h_edges_s=conversion_capture['d2h_edges_s'],filter_qualification=filter_qualification,design=design)
    assert joined_restart['numerical_feedback_converged']
    assert len(joined_restart['converter_stages'])==1
    assert joined_restart['transport']['flow']['d2h_timing']=='explicit_observed_edges'
    assert joined_restart['transport']['flow']['depth_bits']==c['transport']['scheduling']['ingress_bits_per_source']
    rejected=extended_sar_transport(c,dict(joined_restart,numerical_feedback_converged=False),design=design)
    assert rejected['verdict']=='rejected_unconverged_analog_feedback' and rejected['delivered_host_words']==0
    joined_restart.pop('package')
    restart['converter_continuation']=joined_restart
    report=dict(filter_startup=filter_startup,reference_startup=reference_startup_screen(c,design=design),wired_snapshot_service=wired_snapshot_service_check(c,design=design),finite_sar_transport=finite_sar_transport(c,retune,design=design),retained_sar_refinement=refinement,full_package_descriptor_validation=validation,cases=rows,ownership_load_trace=ownership_load_trace(c,design=design),package_handover=package_handover_screen(c,design=design),switching_load_handover=switching_load_handover(c,design=design),full_package_handover=full_package_handover(c,design=design),full_package_adc_handover=full_package_handover(c,adc_current_a=None,design=design),full_package_adc_restart=restart,retained_sar_retune=retune,sources_sha256=hashes,
        scope='The cases field covers loaded selected differential clock edges feeding the independent reference-presence monitor for each engine. Assigned divide-by-64 monitor, 100 ns timeout/10 ns tick, shared startup floor. Gap is a stimulus, not physical source-failure dynamics. Concrete deterministic RX payload, wired TX consumption at selected clock events, and finite host queues run before fault and after recovery. No physical payload waveform, jitter qualification, pad settling, charge-continuous mode handover, converter recovery or startup circuit claim. RF word timestamps use loaded external LO /256 and exclude the injected gap; wired RX remains an independent peer-clock fixture. These cases use synthetic RF words. Actual SAR readiness/delivery is reported separately under retained_sar_retune.extended_lifecycle with its own limitations.')
    if b.baseline_source_hashes()!=hashes:
        raise RuntimeError('Sources changed during lifecycle campaign')
    b.write_evidence(p/'evidence/selected-lifecycle.json',report)
    print(rows)


if __name__=='__main__':main()
