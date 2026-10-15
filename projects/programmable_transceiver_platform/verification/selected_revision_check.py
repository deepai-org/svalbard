"""Extend the revision report with package clocks or matched wired readiness.

Run --wired or --rf for downstream tests; no flag repeats the clock-only screen.
Each new section records its own frozen sources; older sections retain theirs.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import baseline_envelope as b


from design_definition import load_design, DesignDefinition, Scenario


def selected_wifi_exchange_screen(design,*,reference_tools=None):
    """Current FPGA preparation through finite queues; complete HE remains open."""
    from wifi_client_exchange import ClientBench,run
    import numpy as np
    payload=np.random.default_rng(122).integers(0,256,256,dtype=np.uint8).tobytes()
    rows=[]
    target_db=design.architecture['rf_interoperability']['tx_error_allocation']['design_target_db']
    target_fraction=10**(target_db/20)
    for mcs in range(8):
        bench=ClientBench(design=design);bench.mcs=mcs
        try:
            bench.receive_intent('mcs_receive',payload)
            bench.transmit_intent('mcs_reply',payload)
            rows.append(dict(mcs=mcs,completed=True,rows=bench.rows,
                tx_scalar_evm_target_db=target_db,
                tx_scalar_evm_screen_pass=bench.rows[-1]['scalar_observer_evm']<=target_fraction))
        except ValueError as error:
            rows.append(dict(mcs=mcs,completed=False,reason=str(error),rows=bench.rows))
    controls=[]
    for label,mcs in (('short_interpolator',7),('preamble_only_frequency',1)):
        bench=ClientBench(design=design);bench.mcs=mcs
        if label=='short_interpolator':bench.tx_resampler_span=10
        else:bench.track_rx_pilot_cfo=False
        try:
            bench.receive_intent('control_request',payload)
            bench.transmit_intent('control_reply',payload)
            controls.append(dict(label=label,mcs=mcs,completed=True,rows=bench.rows,
                tx_scalar_evm_target_db=target_db,
                tx_scalar_evm_screen_pass=bench.rows[-1]['scalar_observer_evm']<=target_fraction))
        except ValueError as error:
            controls.append(dict(label=label,mcs=mcs,completed=False,reason=str(error),rows=bench.rows))
    from rf_filter_tradeoff import tx_fpga_workload
    policy=design.architecture['rf_interoperability']['fpga_tx_preparation']
    workload=tx_fpga_workload(resampler_span=policy['polyphase_resampler_span'],correction_taps=policy['taps'])
    result=dict(design_provenance=design.provenance(),diagnostic_mcs=rows,diagnostic_controls=controls,fpga_preparation_workload=workload,
        retained_exchange=run(design=design),independent_legacy=None,
        scope='Selected correction and DAC ENOB with charged timing and finite queues. Seeded DATA whitening is diagnostic, not HE scrambling. Prescribed rail/phase and normalized TX remain simplified fixtures; no HE PPDU, PER, watts or emission-mask qualification.')
    if reference_tools is not None:
        from external_wifi_reference import run as independent
        result['independent_legacy']=independent(reference_tools,design=design,tx_data_check=True)
    return result


def rx_gain_regulation_lifecycle(design):
    """Matched selected/adverse gain-law lifecycle; no protocol qualification."""
    from selected_lifecycle import ownership_load_trace
    control=design.hypothetical(reason='Independent unregulated RX gain control',changes={
        'model_assumptions.rf_receive_supply.parameters.gain_supply_elasticity':1.})
    cases=[]
    for label,snapshot in (('selected',design),('unity_gain_control',control)):
        result=ownership_load_trace(snapshot.contract,design=snapshot,wideband=True,
            tx_native_peak=170.,tx_nominal_gain=6.3,shared_stress=True)
        cases.append(dict(label=label,design_provenance=snapshot.provenance(),result=result))
    return dict(cases=cases,scope='Matched retained lifecycle under 60mV 10MHz ripple and fourfold delay sensitivity; assigned broadband RX gain rejection. Diagnostic training, not protocol PER or circuit realization.')


def rf_board_selectivity_screen(design):
    """Check the consistency of full-band loss and selective rejection claims."""
    a=design.architecture
    low,high=a['blocks']['rfpll']['parameters']['vco_hz']
    frontend=a['rf_interoperability']['external_frontend']
    maximum_loss=frontend['rx_insertion_loss_db_max']
    wanted_loss=frontend['rx_insertion_loss_db_nominal']
    divider=min(a['blocks']['clocktree']['parameters']['rf_sample_dividers'])
    rows=[]
    # Independent frequency probes, not standards-derived blockers/mask points.
    for carrier in (low,(low+high)/2,high):
        for label,offset in (('near_blocker',12e6),('outer_tone_dac_image',carrier/divider-9.53125e6)):
            for side in (-1,1):
                frequency=carrier+side*offset
                inside=low<=frequency<=high
                rows.append(dict(carrier_hz=carrier,probe=label,probe_hz=frequency,
                    inside_full_band_board_passband=inside,
                    maximum_absolute_loss_db=maximum_loss if inside else None,
                    maximum_selective_rejection_db_at_nominal_wanted_loss=maximum_loss-wanted_loss if inside else None,
                    assigned_selective_rejection_db=0. if inside else None))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Conditional fixed passive board passing every frequency of the declared carrier band within the shared RX insertion-loss ceiling. Same transfer used at wanted and interfering frequencies; no ideal channel-tracking filter. Probe offsets are diagnostic, not standard compliance points. Out-of-band rejection is unknown, not infinite. No switch/matching S-parameters, emissions or blocker qualification. TX image frequencies illustrate locations only; RX loss allocation is not a TX filter specification.')


def reference_cdr_actuator_screen(design):
    """Necessary phase-slew arithmetic; no data recovery or loop stability claim."""
    a=design.architecture
    steps=a['blocks']['cdr']['parameters']['phase_steps']
    offsets=a['cdr_tracking_requirements']['acquisition_offset_ppm']
    offset=max(abs(x) for x in offsets)*1e-6
    rows=[]
    for rate in a['blocks']['cdr']['parameters']['line_rate_hz']:
        for update_divider in (1,4,8,10,16):
            update=rate/update_divider
            required=steps*rate*offset
            rows.append(dict(line_rate_hz=rate,phase_steps=steps,
                update_every_ui=update_divider,update_hz=update,
                phase_step_s=1/(steps*rate),nearest_phase_error_ui=.5/steps,
                required_single_step_updates_hz=required,
                maximum_offset_ppm_per_single_step=1e6/(steps*update_divider),
                single_step_slew_capacity_sufficient=update>=required,
                phase_wraps_per_second=rate*offset,
                uncorrected_offset_drift_per_update_ui=offset*update_divider))
    # Multi-step commands can use the same phase resolution with a slower
    # control clock. Carry their staircase error rather than treating the
    # additional slew capacity as jitter-free frequency correction.
    for row in rows:
        row['multi_step_options']=[dict(maximum_steps_per_update=n,
            maximum_offset_ppm=n*row['maximum_offset_ppm_per_single_step'],
            slew_capacity_sufficient=n*row['update_hz']>=row['required_single_step_updates_hz'],
            maximum_commanded_phase_jump_ui=n/steps,
            quantization_plus_one_update_drift_ui=.5/steps+offset*row['update_every_ui'],
            quantization_plus_two_update_drift_ui=.5/steps+2*offset*row['update_every_ui'])
            for n in (2,4)]
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        sources=['https://docs.amd.com/r/en-US/am017-versal-gtm-transceivers/RX-CDR',
                 'https://cdrdv2-public.intel.com/654541/dsed8b10b.pdf'],
        scope='Selected phase count, nominal rate endpoints and largest assigned acquisition offset. Compares single-step and two/four-step capacity at unchanged nearest-phase resolution. First-order frequency-to-phase arithmetic; staircase bounds charge one update interval, or two with an additional update latency. These are actuator constraints only: no loop, glitch-free phase switching, interpolation nonlinearity, source jitter, actual latency, saturation trajectory, SSC acceleration, cycle numbering or receiver decisions are simulated. The source timing is not forwarded; phase winding must preserve recovered bit identity. No selected architecture change or current/area credit.')


def usb_pad_separation_screen(design):
    """Optimistic loading benefit, not a fabricated separate-pad design."""
    import sys
    import math
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
    from protocol_pad import SharedWiredPad
    rows=[]
    original=design.architecture
    off=original['pad_behavioral_contract']['shared_wired_network']['inactive_branch_cap_f_per_leg']
    # The aggregate is not identified as USB capacitance. Removing almost all
    # of it deliberately overcredits separation; protection/base loading stays.
    for remaining in (1.,.1,.01):
        a=deepcopy(original)
        network=a['pad_behavioral_contract']['shared_wired_network']
        network['inactive_branch_cap_f_per_leg']=off*remaining
        a['blocks']['wirepad']['parameters']['capacitance_f_per_leg']-=off*(1-remaining)
        pad=SharedWiredPad.from_architecture(a)
        pad.set_external_sources(((.8,50.),(.8,50.)))
        pad.configure('serial')
        pad.advance_network(20e-9,3.3)
        for frequency in (742.5e6,1.25e9,2.5e9):
            transfer=pad.small_signal_transfer(frequency,3.3)['pad_differential']
            rows.append(dict(remaining_inactive_fraction=remaining,frequency_hz=frequency,
                effective_cap_f=a['blocks']['wirepad']['parameters']['capacitance_f_per_leg'],
                magnitude=abs(transfer),phase_rad=math.atan2(transfer.imag,transfer.real)))
    for row in rows:
        baseline=next(x for x in rows if x['remaining_inactive_fraction']==1. and x['frequency_hz']==row['frequency_hz'])
        row['improvement_db']=20*math.log10(row['magnitude']/baseline['magnitude'])
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Assigned linear serial pad network, 50 ohm source per leg, 100 ohm differential termination. Removing 90/99 percent of ALL aggregate inactive branch capacitance overcredits USB separation. Base pad, mutual C, protection obligations and inactive TMDS divider remain. No bond inductance, separate USB topology, area, eye, package or lifecycle qualification. Quantifies this loading mechanism only; does not bound benefits if the assigned decomposition is wrong.')


def shared_pad_envelope(rail_v,*,usb_supply=None,architecture=None,design=None):
    """Connected mode sequence; DC rail from the common ledger, not a PDN proof."""
    import sys
    import numpy as np
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
    from protocol_pad import SharedWiredPad
    if architecture is None:
        if design is None:design=load_design()
        architecture=design.architecture
    elif design is not None and architecture!=design.architecture:
        raise ValueError('Pad architecture conflicts with supplied design')
    if (design is not None and usb_supply is not None and
            usb_supply.get('design_provenance')!=design.provenance()):
        raise ValueError('USB supply conflicts with pad design provenance')
    def make_pad(**overrides):return SharedWiredPad.from_architecture(architecture,**overrides)
    pad=make_pad()
    wired_rail_v=rail_v
    stages=[];transitions=[]
    def record(name):
        state=np.r_[pad.voltage,pad.divider_voltage]
        _,supply,_,_=pad.electrical_network(state,rail_v)
        stages.append(dict(name=name,rail_v=rail_v,pad_v=pad.voltage.tolist(),
            divider_v=pad.divider_voltage.tolist(),local_supply_a=float(supply),
            local_drive=None if pad.local_drive is None else dict(pad.local_drive),
            local_hs_termination_ohm=pad.hs_termination_ohm,
            energy_residual_j=float(pad.network_energy()-pad.source_energy_j
                -pad.external_energy_j+pad.dissipated_j)))
    pad.set_external_sources(((.8,50.),(.8,50.)))
    pad.configure('serial');pad.advance_network(20e-9,rail_v)
    serial=pad.small_signal_transfer(1.25e9,rail_v)
    record('serial_terminated')
    pad.set_external_sources(((3.3,50.),(2.9,50.)))
    transitions.append(pad.transition_mode('tmds',command_delay_s=2e-9,dead_time_s=3e-9,rail=rail_v))
    pad.advance_network(40e-9,rail_v)
    tmds=pad.small_signal_transfer(742.5e6,rail_v)
    record('tmds_loaded_divider')
    transitions.append(pad.transition_mode('isolated',command_delay_s=0.,dead_time_s=3e-9,rail=rail_v))
    pad.advance_network(60e-9,rail_v)
    record('reset_with_external_tmds_source_retained')
    pad.set_external_sources((None,None))
    if usb_supply is not None:rail_v=usb_supply['ledger']['local_payload_clock_core_rail_v']
    transitions.append(pad.transition_mode('usb',speed='hs',command_delay_s=2e-9,dead_time_s=3e-9,rail=rail_v))
    pad.set_local_passives(termination_ohm=(pad.hs_termination_ohm,)*2)
    pad.set_peer_passives(termination_ohm=(45.,45.))
    pad.set_local_drive('current',node=0)
    pad.advance_network(80e-9,rail_v);record('usb_current_drive')
    pad.set_local_drive('off');pad.advance_network(100e-9,rail_v)
    record('usb_release')
    # An adverse protection topology is retained through power loss. Omitting
    # this clamp above is not evidence for the proposed fail-safe protection.
    adverse=make_pad(rail_clamp=(.4,20.))
    adverse.set_external_sources(((3.3,50.),(3.3,50.)))
    adverse.advance_network(20e-9,0.)
    _,backfeed,_,_=adverse.electrical_network(
        np.r_[adverse.voltage,adverse.divider_voltage],0.)
    # Candidate primary protection is independent of VDD. Keep its finite
    # resistance: a threshold is not a guaranteed maximum terminal voltage.
    independent=make_pad(positive_ground_clamp=(3.6,20.),ground_clamp=(.4,20.))
    independent.configure('tmds')
    independent.set_external_sources(((3.3,50.),(3.3,50.)))
    independent.advance_network(20e-9,rail_v)
    independent.configure('isolated')
    protection=[]
    for index,(name,source,rail) in enumerate((
            ('unpowered_normal_peer',3.3,0.),
            ('unpowered_overvoltage_peer',4.5,0.),
            ('powered_overvoltage_peer',4.5,rail_v))):
        independent.set_external_sources(((source,50.),(source,50.)))
        independent.advance_network((index+2)*20e-9,rail)
        state=np.r_[independent.voltage,independent.divider_voltage]
        _,supply,_,loss=independent.electrical_network(state,rail)
        protection.append(dict(name=name,rail_v=rail,external_source_v=source,
            pad_v=independent.voltage.tolist(),divider_v=independent.divider_voltage.tolist(),
            isolated_branch_voltage_v=(independent.voltage-independent.divider_voltage).tolist(),
            backfeed_a=max(0.,float(-supply)),dissipation_w=float(loss),
            exceeds_assigned_3p6v_terminal_screen=bool(max(independent.voltage)>3.6),
            energy_residual_j=float(independent.network_energy()-independent.source_energy_j-
                independent.external_energy_j+independent.dissipated_j)))
    power_cycles=[]
    for topology,kwargs in (
            ('rail_clamp_control',dict(rail_clamp=(.4,20.))),
            ('ground_primary_candidate',dict(positive_ground_clamp=(3.6,20.),ground_clamp=(.4,20.)))):
        for ramp in (5e-9,50e-9):
            probe=make_pad(**kwargs)
            probe.set_external_sources(((3.3,50.),(3.3,50.)))
            probe.configure('tmds');probe.advance_network(20e-9,wired_rail_v)
            probe.transition_mode('isolated',command_delay_s=0.,dead_time_s=3e-9,rail=wired_rail_v)
            origin=probe.time;initial_charge=probe.supply_backfeed_charge_c
            stages_power=[]
            for name,duration,begin,end in (('fall',ramp,wired_rail_v,0.),('off',20e-9,0.,0.),
                                          ('rise',ramp,0.,wired_rail_v)):
                start=probe.time
                forcing=lambda t,a=start,d=duration,v0=begin,v1=end:v0+(v1-v0)*min(1.,max(0.,(t-a)/d))
                result=probe.advance_network(start+duration,forcing,max_step_s=min(ramp/40,1e-9))
                stages_power.append(dict(name=name,**result))
            power_cycles.append(dict(topology=topology,ramp_duration_s=ramp,start_s=origin,
                stages=stages_power,supply_backfeed_charge_c=probe.supply_backfeed_charge_c-initial_charge,
                final_nodes_v=np.r_[probe.voltage,probe.divider_voltage].tolist(),
                energy_residual_j=float(probe.network_energy()-probe.source_energy_j-
                    probe.external_energy_j-probe.injection_energy_j+probe.dissipated_j)))
    charge_cases=[]
    for target in ('isolated','tmds'):
        for equivalent_cap in (0.,10e-15,50e-15):
            for duration in (50e-12,200e-12):
                for sign in (-1.,1.):
                    probe=make_pad()
                    probe.set_external_sources(((3.3,50.),(2.9,50.)))
                    probe.configure('tmds' if target=='isolated' else 'isolated')
                    probe.advance_network(20e-9,wired_rail_v)
                    q=sign*equivalent_cap*3.3
                    packets=[[q,-q,q,-q],[q,-q,q,-q]]
                    transition=probe.transition_mode(target,command_delay_s=2e-9,dead_time_s=3e-9,
                        rail=wired_rail_v,edge_charge_c=packets,injection_duration_s=duration)
                    pulses=[transition['break_pulse'],transition['make_pulse']]
                    charge_cases.append(dict(target=target,equivalent_control_coupling_f=equivalent_cap,
                        control_swing_v=3.3,polarity=sign,pulse_duration_s=duration,
                        sampled_node_min_v=np.min([x['sampled_node_min_v'] for x in pulses],axis=0).tolist(),
                        sampled_node_max_v=np.max([x['sampled_node_max_v'] for x in pulses],axis=0).tolist(),
                        injection_work_j=probe.injection_energy_j,
                        energy_residual_j=float(probe.network_energy()-probe.source_energy_j-
                            probe.external_energy_j-probe.injection_energy_j+probe.dissipated_j)))
    internal_protection=[]
    for drop in (.4,.7):
        for resistance in (20.,100.):
            for capacitance in (10e-15,30e-15):
                for sign in (-1.,1.):
                    probe=make_pad(divider_ground_clamp=(drop,resistance),
                        divider_clamp_cap_f=capacitance)
                    probe.set_external_sources(((3.3,50.),(2.9,50.)))
                    probe.configure('tmds');probe.advance_network(20e-9,wired_rail_v)
                    gain=abs(probe.small_signal_transfer(742.5e6,wired_rail_v)['divider_differential'])
                    q=sign*50e-15*3.3
                    transition=probe.transition_mode('isolated',command_delay_s=2e-9,dead_time_s=3e-9,
                        rail=wired_rail_v,edge_charge_c=[[q,-q,q,-q]]*2,injection_duration_s=50e-12)
                    pulses=[transition['break_pulse'],transition['make_pulse']]
                    low=np.min([x['sampled_node_min_v'] for x in pulses],axis=0)
                    state=np.r_[probe.voltage,probe.divider_voltage]
                    _,supply,_,_=probe.electrical_network(state,0.)
                    internal_protection.append(dict(drop_v=drop,resistance_ohm=resistance,
                        added_capacitance_per_node_f=capacitance,polarity=sign,
                        divider_gain_at_742p5mhz=gain,
                        gain_change_db=20*np.log10(gain/abs(tmds['divider_differential'])),
                        sampled_divider_min_v=low[2:].tolist(),
                        sampled_peak_ground_to_divider_a=probe.internal_clamp_current(low[2:]).tolist(),
                        integrated_ground_to_divider_charge_c=probe.divider_clamp_charge_c.tolist(),
                        final_state_zero_supply_backfeed_a=max(0.,float(-supply)),
                        energy_residual_j=float(probe.network_energy()-probe.source_energy_j-
                            probe.external_energy_j-probe.injection_energy_j+probe.dissipated_j)))
    return dict(design_provenance=None if design is None else design.provenance(),
        model_role='independent_pad_fixture' if design is None else 'shared_design_static_rail_pad_sequence',
        imposed_wired_rail_v=wired_rail_v,
        rail_v=wired_rail_v,usb_supply=usb_supply,stages=stages,transitions=transitions,
        power_cycles=dict(cases=power_cycles,scope='External3.3V/50ohm sources retained through explicit isolation then finite rail fall/off/rise. Rail is forced and can absorb reverse current; this does not predict a floating or back-powered supply voltage. Recorded backfeed charge/current, sampled node extrema and energy balance; no automatic brownout-isolation delay, switch stress or missing junction proof.'),
        internal_protection=dict(cases=internal_protection,
            scope='Finite ground-referenced negative clamp and explicit added capacitance on each divider node. Same50fF-equivalent charge and50ps pulses through TMDS-to-isolated change with retained external drive. Full Cartesian drop/resistance/capacitance/polarity sweep. Sampled minima and current peaks, integrated return charge; no physical diode/ESD/positive clamp/leakage/ground-bounce model. Zero-supply backfeed is a final-state topology check, not a power-collapse transient. No cost or safe stress verdict.'),
        switch_charge=dict(cases=charge_cases,node_order=['pad_p','pad_n','divider_p','divider_n'],
            scope='Assigned signed charge=equivalent control coupling times3.3V, on each of four nodes at break and make. Finite constant-current pulses, both polarities and two widths, retained external drive. No measured switch parameters, exhaustive correlations, internal clamps, oxide-stress limits or continuous-time extrema guarantee. Injection work is separate from chip/peer supply work; physical control-driver power remains unallocated.'),
        serial_pad_gain_at_1p25ghz=abs(serial['pad_differential']),
        tmds_divider_gain_at_742p5mhz=abs(tmds['divider_differential']),
        adverse_unpowered_backfeed_a=float(-backfeed),
        ground_referenced_protection=dict(threshold_v=3.6,dynamic_resistance_ohm=20.,cases=protection,
            scope='Assigned shunt law, capacitance already in pad hypothesis. 3.6V is a diagnostic terminal screen, not a GF180 absolute maximum. No ESD trigger/holding/thermal or internal transistor terminal model.'),
        physical_protection_qualified=False,
        scope='One retained four-node network across serial, TMDS, reset and USB. '
        'DC rail uses the wired common ledger, with a separate USB allocation when supplied. '
        'The change of supply operating point is imposed, not a regulator/PDN transient. '
        'Small-signal transfer excludes package inductance. '
        'Assigned divider and clamp values; no ESD, oxide stress or safe protection proof. '
        'Mode transitions include assigned command delay and break-before-make interval. Separate finite charge-pulse hypotheses probe injection; transistor switch edges, skew and physical slew remain open.')


def usb_inventory_supply(contract,architecture,*,return_l=None,die_esl=None,design=None):
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('USB supply documents conflict with supplied design snapshot')
    scenario=Scenario()
    overrides={}
    if return_l is not None:overrides['package_return_inductance_h']=return_l
    if die_esl is not None:overrides['die_decoupling_esl_h']=die_esl
    if overrides:scenario=scenario.override(reason='Explicit USB package uncertainty probe',**overrides)
    env,context=b.usb_supply_environment(design,scenario=scenario)
    ledger=b.partitioned_dc_ledger(env,dict(link_r_ohm=1e-5))
    return dict(context,inventory=env['inventory_current_report'],ledger=ledger,
        host_word_hz=context['resolved_configuration']['host_word_hz'],output_cap_f=env['host_spectrum']['output_cap_f'],
        scope='USB inventory ceiling through common DC network; no activity shutdown credit, '
        'no delivered USB clock or dynamic package feedback qualification.')



def shared_pad_design_screen(design):
    """Mode-exclusive pad screen with both owner budgets from one snapshot."""
    config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
    scenario=Scenario()
    raw=b.configured_environment(config,scenario)
    environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
                 scenario_overrides=scenario.record(),clock=clock)
    if environment is None:
        return dict(context,status='rejected_wired_clock',pad=None)
    usb=usb_inventory_supply(design.contract,design.architecture,design=design)
    result=shared_pad_envelope(clock['ledger']['local_payload_clock_core_rail_v'],
        usb_supply=usb,architecture=design.architecture,design=design)
    result.update(context)
    result['usb_resolved_configuration']=usb['resolved_configuration']
    result['model_role']='shared_design_static_rail_pad_sequence'
    return result


def validate_saved_design_input(report,design,*,engine,direction):
    """Require current bound evidence before deriving another chip conclusion."""
    from check_contract import verify_reported_configuration
    if report.get('design_provenance')!=design.provenance():
        raise ValueError('Saved input design provenance missing or mismatched; regenerate input')
    configuration=verify_reported_configuration(design,report.get('resolved_configuration'))
    if configuration.engine!=engine or configuration.direction!=direction:
        raise ValueError('Saved input configuration has the wrong engine or direction')
    manifest=report.get('sources_sha256')
    required=b.baseline_source_hashes()
    if not isinstance(manifest,dict) or not required.keys()<=manifest.keys():
        raise ValueError('Saved input source manifest incomplete; regenerate input')
    for name,digest in manifest.items():
        source=b.P/name
        if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
            raise ValueError('Saved input sources changed; regenerate input')
    return configuration


def usb_trim_envelope(packet_report,architecture):
    """Fast static inverse screen of the inventory current-trim control."""
    import numpy as np
    rails=packet_report['conservative_rail_interval_v']
    source=architecture['model_assumptions']['wired_pad_driver']['parameters']
    network=architecture['pad_behavioral_contract']['shared_wired_network']
    usb=architecture['blocks']['usbhs']['parameters']
    local_bounds=[.95*usb['termination_ohm_per_leg'],1.05*usb['termination_ohm_per_leg']]
    peer_bounds=[42.75,47.25]  # Independent precision-load uncertainty fixture.
    architecture_hash=hashlib.sha256(json.dumps(architecture,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    provenance=packet_report.get('design_provenance')
    if provenance is not None and provenance.get('documents',{}).get('spec/analog-architecture.json')!=architecture_hash:
        raise ValueError('USB trim packet and architecture provenance conflict')
    target=(.36,.44)  # Existing illustrative swing gate, not a compliance mask.
    control=architecture['control_fields']['usbhs.config']['fields']['current_code']
    code_values=np.arange(control['minimum'],control['maximum']+1)
    codes=.8+.4*code_values/((1<<control['bits'])-1);rows=[]
    for resistance in (250.,1000.,5000.):
        for sensitivity in (-.5,-.2,0.,.2,.5,.8):
            candidates=[]
            for code,trim in zip(code_values,codes):
                voltages=[]
                for rail in rails:
                    for local in local_bounds:
                        for peer in peer_bounds:
                            conductance=1/local+1/peer+1/source['shunt_leakage_ohm']+1/(network['divider_off_ohm']+network['divider_bottom_ohm'])
                            current=usb['drive_current_a']*trim*(1+sensitivity*(rail-source['reference_supply_v']))
                            voltage=(current+source['reference_pad_v']/resistance)/(conductance+1/resistance)
                            if voltage<0 or rail-voltage<source['compliance_headroom_v']:
                                raise ValueError('Static screen outside active current-source law')
                            voltages.append(voltage)
                low,high=min(voltages),max(voltages)
                candidates.append(dict(code=int(code),trim=float(trim),voltage_interval_v=[low,high],
                    margin_v=min(low-target[0],target[1]-high)))
            best=max(candidates,key=lambda x:x['margin_v'])
            admitted=[x['code'] for x in candidates if x['margin_v']>=0]
            rows.append(dict(output_resistance_ohm=resistance,supply_fraction_per_v=sensitivity,
                admissible_codes=admitted,best=best,admitted=bool(admitted)))
    return dict(rail_interval_v=list(rails),local_termination_interval_ohm=local_bounds,
        input_packet_context={key:deepcopy(packet_report[key]) for key in (
            'design_provenance','resolved_configuration','scenario_overrides',
            'scenario_assumptions','operating_conditions','diagnostic_intervention') if key in packet_report},
        remote_termination_interval_ohm=peer_bounds,architecture_sha256=architecture_hash,
        input_scope='shared_design_packet' if provenance is not None else 'unbound_packet_fixture',
        nominal_drive_current_a=usb['drive_current_a'],
        illustrative_voltage_gate_v=list(target),trim_range=[.8,1.2],trim_bits=control['bits'],cases=rows,
        input_packet_report_sha256=hashlib.sha256(json.dumps(packet_report,sort_keys=True).encode()).hexdigest(),
        input_sources_sha256=deepcopy(packet_report['sources_sha256']),
        scope='One fixed quantized code across bounded rail and independent +/-5percent terminations. '
        'Static finite-source law; extrema at interval endpoints for each assigned source hypothesis. '
        'Not switching extrema, USB compliance, physical source bounds or calibrated board evidence.')


def usb_common_packet_screen(contract,architecture,*,design=None):
    """USB pad/transport driven by the shared host-current/package network."""
    import numpy as np
    from behavioral import BehavioralChip
    from dataclasses import replace
    from selected_lifecycle import selected_transport_assumptions
    from resource_configuration import encode_resource_word
    from protocol_pad import SharedWiredPad
    from usb_selected_timing import reply_trace,DirectHostState
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('USB packet documents conflict with supplied design snapshot')
    config=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
        host_clock_source='host_follow',host_input_hz=architecture['direct_stream_service']['budget']['host_hz'],
        wired_pad_path='bidirectional')
    scenario=Scenario()
    env=b.configured_environment(config,scenario)
    # Keep full HOST DC allocation. The harmonic helper remains a DDR-shaped
    # pulse surrogate at this word rate, not the selected SDR clock waveform.
    env['host_spectrum']['h2d_word_hz']=config.host_word_hz
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),model_assumptions=dict(
            startup='Prequalified; zero-delay harness, no startup evidence',
            host_current='DDR-shaped harmonic surrogate at selected word rate; not SDR waveform qualification',
            current_source='Per-case explicitly assigned ideal/finite pad hypotheses'))
    ledger=b.partitioned_dc_ledger(env,dict(link_r_ohm=1e-5))
    tones=[]
    for frequency,injection in b.partitioned_host_sources(env).items():
        solved=b.partitioned_return_solution(frequency,env['network'],injection,link_r_ohm=1e-5)
        voltage=solved['voltage'][1]-solved['voltage'][3]
        tones.append(dict(frequency_hz=frequency,peak_v=float(abs(voltage)),phase_rad=float(np.angle(voltage))))
    omega=2*np.pi*np.array([x['frequency_hz'] for x in tones])
    phasors=np.array([x['peak_v']*np.exp(1j*x['phase_rad']) for x in tones])
    dc=ledger['local_payload_clock_core_rail_v']
    rail=lambda t:float(dc+np.real(np.exp(1j*omega*t)@phasors))
    rows=[]
    for name,subdivisions,law in (
            ('shared_driver_baseline',16,{}),('shared_driver_baseline',32,{}),
            ('finite_untrimmed',32,dict(output_resistance_ohm=1000.,supply_fraction_per_v=.5)),
            ('finite_max_trim',32,dict(output_resistance_ohm=1000.,supply_fraction_per_v=.5,trim=1.2))):
        # Startup is prequalified for this packet-only experiment; do not
        # mislabel a zero-delay lifecycle harness as analog startup evidence.
        chip=BehavioralChip(replace(selected_transport_assumptions(env),startup_s=0.))
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=config.line_rate_bps));chip.configure_transport('direct')
        pad=SharedWiredPad.from_architecture(architecture,current_source=law);pad.configure('usb',speed='hs')
        pad.set_local_passives(termination_ohm=(pad.hs_termination_ohm,)*2)
        pad.set_peer_passives(termination_ohm=(45.,45.))
        step=1/(subdivisions*max(x['frequency_hz'] for x in tones))
        chip.attach_wired_pad(pad,rail_source=rail,max_step_s=step)
        chip.start();chip.advance(chip.ready_at)
        host=DirectHostState(chip)
        result=reply_trace(chip=chip,configuration=config,host_state=host,payload=b'A')
        chip.stop()
        rows.append(dict(name=name,current_source={k:(float(v) if np.isfinite(v) else "infinite_ideal_control") for k,v in pad.current_source.items()},subdivisions=subdivisions,max_step_s=step,result=result,
            energy_residual_j=pad.network_energy()-pad.source_energy_j-pad.external_energy_j+pad.dissipated_j,
            output_released=pad.local=='Z',final_pad_v=pad.voltage.tolist()))
    return dict(context,inventory=env['inventory_current_report'],ledger=ledger,host_word_hz=config.host_word_hz,
        rail_tones=tones,conservative_rail_interval_v=[dc-sum(x['peak_v'] for x in tones),dc+sum(x['peak_v'] for x in tones)],
        cases=rows,scope='Actual USB inventory and common five-node host/package forcing feed retained pad and finite direct transport. '
        'Host-only harmonic forcing; core/timing switching, USB load-to-PDN feedback, clock/capture delay and acquisition are not solved. '
        'Startup prequalified with zero harness delay; not a whole-system startup or USB compliance verdict.')


def wired_receiver_environment(contract,architecture,*,design=None,cdr_periodic_tracking=False):
    """Resolve current wired RX inventory without embedding package defaults."""
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('Wired receiver documents conflict with supplied design snapshot')
    config=design.configure(engine='wire',direction='rx',reference_hz=2.5e9,host_divider=8,
        cdr_periodic_tracking=cdr_periodic_tracking)
    scenario=Scenario()
    environment=b.configured_environment(config,scenario)
    return environment,dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),model_assumptions=dict(
            result_role='cdr_candidate_comparison',
            reason='Explicit loop/noise/coupling candidates, not proven selectable circuit settings',
            channel_capacitance_f=2.7e-12,channel_time_constant_s=100e-12,
            ctle_zero_s=200e-12,ctle_pole_s=80e-12,holdover_ui=512))


def cdr_tuning_screen(contract,architecture,*,design=None):
    """Short local SSC-slope comparison; not a replacement for full-cycle qualification."""
    import numpy as np
    env,context=wired_receiver_environment(contract,architecture,design=design)
    trial,clock=b.reference_payload_environment(env,dict(link_r_ohm=1e-5),False)
    if trial is None:return dict(context,cases=[],clock=clock,status='clock_rejected')
    base=dict(b.wired_shared_impairment(trial),name='cdr_tuning',
              ctle_zero_s=200e-12,ctle_pole_s=80e-12,holdover_ui=512)
    count=6000;bits=np.random.default_rng(9023).integers(0,2,count).tolist()
    bits[4000:4192]=[0]*192
    rows=[]
    for phase_gain,frequency_gain,noise,window,average,fit in (
            (.15,.0002,5e-12,0,1.,'interval'),(.08,.0002,5e-12,512,1.,'interval'),
            (.08,.0002,5e-12,128,1.,'least_squares'),(.08,.0002,5e-12,256,1.,'least_squares'),
            (.08,.0002,1e-12,128,1.,'least_squares'),(.08,.0002,1e-12,256,1.,'least_squares')):
        for sign in (-1,1):
            ppm=sign*np.arange(count)*300e6/2.5e9
            edges=np.r_[0.,np.cumsum(1/(2.5e9*(1+ppm*1e-6)))]
            impairment=dict(base,phase_gain=phase_gain,frequency_gain=frequency_gain,
                            detector_noise_rms_s=noise,frequency_window_ui=window,frequency_average_gain=average,frequency_fit=fit)
            result=b.causal_receiver_envelope(timing_scenarios=[impairment],
                channel_cases=((2.7e-12,100e-12),),source_bits=bits,source_edges_s=edges,
                initial_conditions=((.35,100.),))
            rows.append(dict(phase_gain=phase_gain,frequency_gain=frequency_gain,
                detector_noise_rms_s=noise,frequency_window_ui=window,frequency_average_gain=average,frequency_fit=fit,
                source_slope_ppm_s=sign*300e6,result=result))
    return dict(context,cases=rows,clock=clock,source_bits=count,gap_start_bit=4000,gap_length_ui=192,
        scope='Same inventory supply/channel/aperture, two local frequency ramps and one gap. '
        'Assigned loop/noise hypotheses; no physical current or realizability proof. '
        'Not complete SSC excursion/cycles, jitter-mask, protocol or continuous uncertainty qualification.')


def phase_bank_tracking_screen(design,*,bins=24,phase_gain=.06,frequency_gain=.0006,slope_gain=2e-6,frequency_window_ui=0,frequency_fit="interval",frequency_fit_hop_ui=0,large_error_phase_gain=0.,phase_error_threshold_ui=.03125,detector_noise_rms_s=None,full_cycles=False,source_seed=9023,source_phase_cycles=None,source_bit_count=None,inserted_gaps=None,phase_observation_sink=None,periodic_clock_compute_delay_s=None,scored_start_bit=1200,initial_local_offset_ppm=None,_receiver_from_design=False):
    """Unselected local-sampler SSC/gap experiment; assigned acquired initial state."""
    import numpy as np
    env,context=wired_receiver_environment(design.contract,design.architecture,design=design,
        cdr_periodic_tracking=_receiver_from_design)
    trial,clock=b.reference_payload_environment(env,dict(link_r_ohm=1e-5),False)
    if trial is None:return dict(context,status='clock_rejected',clock=clock)
    count=170000 if full_cycles else 24000;rate=2.5e9;seed=source_seed
    if source_bit_count is not None:
        if type(source_bit_count) is not int or source_bit_count<2600:raise ValueError('At least2600 source bits required')
        count=source_bit_count
    phase=(0. if full_cycles else .45) if source_phase_cycles is None else source_phase_cycles
    if type(seed) is not int or seed<0 or not np.isfinite(phase):raise ValueError('Valid source seed and finite SSC phase required')
    bits=np.random.default_rng(seed).integers(0,2,count).tolist()
    gaps=((25000,192),(65000,512),(105000,512),(145000,192)) if full_cycles else ((9000,512),(18000,192))
    if inserted_gaps is not None:gaps=tuple(inserted_gaps)
    if any(type(i) is not int or type(n) is not int or i<1 or n<1 or i+n+1>=count for i,n in gaps):
        raise ValueError('Gaps must lie inside the source record')
    for start,length in gaps:
        bits[start-1:start+length+1]=[1]+[0]*length+[1]
    source_ppm=-5000*(1-np.abs(2*((np.arange(count)*30e3/rate+phase)%1)-1))
    edges=np.r_[0.,np.cumsum(1/(rate*(1+source_ppm*1e-6)))]
    initial_ppm=(1/(1+source_ppm[0]*1e-6)-1)*1e6+100 if initial_local_offset_ppm is None else float(initial_local_offset_ppm)
    if not np.isfinite(initial_ppm):raise ValueError("Finite local clock offset required")
    if detector_noise_rms_s is None:detector_noise_rms_s=design.architecture['blocks']['cdr']['parameters']['detector_jitter_rms_s']
    controls=dict(b.wired_shared_impairment(trial),name='unselected_sampled_phase_bank',
        detector_model='phase_bank',detector_phase_bins=bins,detector_phase_span_ui=.375,
        large_error_phase_gain=large_error_phase_gain,phase_error_threshold_ui=phase_error_threshold_ui,
        phase_gain=phase_gain,frequency_gain=frequency_gain,frequency_slope_gain=slope_gain,
        frequency_window_ui=frequency_window_ui,frequency_fit=frequency_fit,frequency_fit_hop_ui=frequency_fit_hop_ui,
        detector_noise_rms_s=detector_noise_rms_s,
        periodic_clock_compute_delay_s=periodic_clock_compute_delay_s,
        acquisition_ui=1000000 if periodic_clock_compute_delay_s is not None else 1024,
        holdover_ui=512,holdover_residual_ppm=125.,bound_aperture_motion=True,
        ctle_zero_s=design.architecture['blocks']['ctle']['parameters']['zero_s'],
        ctle_pole_s=design.architecture['blocks']['ctle']['parameters']['pole_s'])
    channel=(2.7e-12,100e-12)
    if _receiver_from_design:
        resolved=b.baseline_wired_receiver_inputs(trial,label='configured_phase_bank_candidate')
        controls=resolved['timing_scenario'];channel=resolved['channel_case']
        if controls['detector_model']!='phase_bank':raise ValueError('Configured phase-bank design required')
    bins=controls['detector_phase_bins'];span=controls['detector_phase_span_ui']
    result=b.causal_receiver_envelope(timing_scenarios=[controls],channel_cases=(channel,),
        source_bits=bits,source_edges_s=edges,initial_conditions=((.35,float(initial_ppm)),),
        phase_observation_sink=phase_observation_sink,scored_start_bit=scored_start_bit)
    return dict(context,result=result,clock=clock,prototype_controls=controls,
        required_tracking_samplers=bins+2,required_nominal_phase_steps=bins/(2*span),
        receiver_parameters_from_design=_receiver_from_design,channel_case=channel,
        full_cycles=full_cycles,inserted_gaps=[dict(start_bit=i,length_ui=n) for i,n in gaps],
        source_seed=seed,source_phase_cycles=phase,
        source_bits=count,source_modulation_hz=30000.,source_downspread_ppm=5000.,
        initial_clock_offset_ppm=float(initial_ppm),initial_clock_source='source_derived_fixture' if initial_local_offset_ppm is None else 'independent_local_clock',selected=_receiver_from_design,
        scope='Received local comparator bits and nominal phase slots only; no source timing enters feedback. Phase bank and optional periodic predictor are selected mathematical hardware; sampler current/loading/area and actuator implementation remain unqualified. Initial-clock provenance is recorded separately; recorded trajectory/gaps determine scope. Cold acquisition, actuator latency, independent seeds/SSC phases and physical compatibility unqualified.')


def configured_phase_bank_tracking_screen(design,**stimulus):
    """Shared receiver hardware; only independent source/scoring settings vary."""
    allowed={'full_cycles','source_seed','source_phase_cycles','source_bit_count',
             'inserted_gaps','phase_observation_sink','scored_start_bit','initial_local_offset_ppm'}
    if set(stimulus)-allowed:raise ValueError('Change receiver hardware in the design snapshot, not the stimulus')
    return phase_bank_tracking_screen(design,_receiver_from_design=True,**stimulus)


def selected_cdr_tracking_screen(design, *, source_seed=9024, source_phase_cycles=.217, cold=False):
    """Acquired-state shared-design acceptance, with independent source scoring."""
    report=configured_phase_bank_tracking_screen(design,full_cycles=True,
        source_seed=source_seed,source_phase_cycles=source_phase_cycles,
        source_bit_count=430000,inserted_gaps=((65000,512),(315000,512),(356666,512),(398333,512)),
        scored_start_bit=350000,initial_local_offset_ppm=0. if cold else None)
    target=design.architecture['cdr_traffic_requirements']['selected_budget']['qualified_residual_frequency_error_target_ppm']
    cases=report.get('result',{}).get('cases',[])
    for case in cases:
        checks=dict(zero_errors=case['heldout_errors']==0,
            policy_valid=case['heldout_policy_valid_fraction']==1.,
            qualified=case['heldout_qualified_fraction']==1.,
            no_losses=case['qualification_losses']==0,
            tracking_frequency_target=case['heldout_free_run_residual_abs_ppm_quantiles'][-1]<=target)
        if cold:
            checks['timely_cold_acquisition']=case['first_qualified_bit'] is not None and case['first_qualified_bit']<=report['prototype_controls']['acquisition_ui']
            link=case['periodic_clock_controller']['observation_link']
            checks['bounded_observation_queue']=link['fault'] is None and link['peak_chip_queue_bits']<=link['queue_capacity_bits']
        case['tracking_frequency_target_ppm']=target
        case['selected_tracking_checks']=checks
        case['selected_tracking_pass']=all(checks.values())
    report['selected_tracking_pass']=bool(cases) and all(c['selected_tracking_pass'] for c in cases)
    report['model_assumptions']['result_role']='selected_cdr_cold_acquisition_acceptance' if cold else 'selected_cdr_acquired_state_acceptance'
    report['model_assumptions']['reason']='Hardware and transport resolve from shared configuration; nominal independent local clock' if cold else 'Hardware and transport resolve from shared configuration; coarse initial frequency remains a fixture'
    return report


def cdr_phase_bank_candidate(design):
    """Compatibility entry point: the phase bank is now the shared design."""
    if design.architecture['blocks']['cdr']['parameters']['detector_model']!='phase_bank':
        raise ValueError('Selected phase-bank design required')
    return design


def periodic_clock_acquisition_screen(design):
    """Learn from local sampler output; score future clocks without feeding back truth."""
    import numpy as np
    from timing_services import fit_periodic_clock,periodic_clock_period_prediction,periodic_clock_elapsed
    observations=[];next_observation=2048
    def capture(local_count,measured_edge):
        nonlocal next_observation
        if len(observations)<128 and local_count>=next_observation:
            observations.append((local_count,measured_edge))
            next_observation=local_count+2048
    count=340000;rate=2.5e9;phase=.217;seed=9024
    gaps=((25000,192),(65000,512),(105000,512),(145000,192),(315000,512))
    receiver=phase_bank_tracking_screen(design,bins=96,phase_gain=.04,
        frequency_gain=.0003,slope_gain=5e-7,detector_noise_rms_s=.5e-12,
        full_cycles=True,source_seed=seed,source_phase_cycles=phase,
        source_bit_count=count,inserted_gaps=gaps,phase_observation_sink=capture)
    if len(observations)!=128:return dict(receiver=receiver,status='insufficient_observations',observations=observations)
    fit=fit_periodic_clock(observations,line_hz=rate)
    # Source phase, source periods and scoreboard alignment exist only below
    # this boundary, for independent scoring. The learner never receives them.
    case=receiver['result']['cases'][0];lag=case['scoreboard_fixed_lag_bits']
    source_cycles=np.arange(count)
    source_periods=1/(1-5000e-6*(1-abs(2*((source_cycles*30e3/rate+phase)%1)-1)))
    first=int(fit['last_observed_cycle'])+1
    future=np.arange(first,count-200-max(0,lag))
    predictions=periodic_clock_period_prediction(fit,future)
    residual=(source_periods[future+lag]/predictions-1)*1e6
    gap_rows=[]
    for start,length in gaps:
        local=start-lag
        if local<=fit['last_observed_cycle']:continue
        intervals=np.arange(local,local+length+1)-fit['origin_cycle']
        elapsed=periodic_clock_elapsed(intervals,**{k:fit[k] for k in
            ('period_ui','phase_cycles','offset_ppm','depth_ppm')})
        predicted_drift=elapsed-elapsed[0]
        true_drift=np.r_[0.,np.cumsum(source_periods[start:start+length])]
        gap_rows.append(dict(start_source_cycle=start,length_ui=length,
            peak_period_prediction_error_ppm=float(max(abs((source_periods[start:start+length]/
                periodic_clock_period_prediction(fit,np.arange(local,local+length))-1)*1e6))),
            peak_integrated_prediction_error_ui=float(max(abs(predicted_drift-true_drift)))))
    target=design.architecture['cdr_traffic_requirements']['selected_budget']['qualified_residual_frequency_error_target_ppm']
    return dict(receiver=receiver,observations=observations,fit=fit,
        acquisition_observation_time_s=fit['last_observed_edge_ui']/rate,
        future_sample_count=len(future),future_residual_abs_ppm_quantiles=np.quantile(abs(residual),[.5,.95,1.]).tolist(),
        future_tracking_target_ppm=target,future_tracking_target_pass=bool(max(abs(residual))<=target),
        future_gaps=gap_rows,selected=False,feedback_integrated=False,
        scope='Fixed128 local observations; first96 fit and last32 validate before future scoring. Learner receives no source waveform, modulation phase, labels or future samples. Original receiver still drives all sampling; fitted prediction is not yet a clock actuator. Acquisition/compute latency, runtime invalidation, fixed-point storage and uncertainty guarantees remain open.')


def cdr_window_candidate(design):
    """One explicit hypothetical circuit, including its fourth sampler port.

    The selected four-sampler design is returned unchanged. Legacy three-sampler
    fixtures receive the explicit structural extension once; numeric variants
    can use hypothetical().
    """
    a=design.architecture
    slicer=a['blocks']['slicer'];cdr=a['blocks']['cdr']
    if slicer['parameters'].get('tracking_sampler_count')==4:
        cdr_window_controls(design)
        return design
    if cdr['parameters'].get('detector_model')=='phase_bank':
        slicer['parameters']['tracking_sampler_count']=4
        cdr['parameters'].update(detector_model='early_late',phase_gain=1/512,
            frequency_gain=1/131072,frequency_slope_gain=0.,detector_jitter_rms_s=2e-12,
            periodic_clock_compute_delay_s=None,periodic_observation_link=None)
        return DesignDefinition.from_documents(design.contract,a)
    if 'sample_boundary' in a['nets'] or 'boundary' in slicer['ports']:
        raise ValueError('Incomplete four-sampler topology')
    slicer['parameters']['tracking_sampler_count']=4
    slicer['parameters']['topology']='Four tracking regenerative samplers (DATA, central boundary, two window samples) plus eight gated burst-acquisition samplers'
    slicer['resource_allocation']['current_budget_ma']['wired']+=4.
    slicer['outputs'].append('boundary')
    slicer['ports']['boundary']=dict(direction='out',net='sample_boundary',contract='sample_boundary')
    cdr['inputs'].append('boundary')
    cdr['ports']['boundary']=dict(direction='in',net='sample_boundary',contract='sample_boundary')
    a['nets']['sample_boundary']=json.loads(json.dumps(a['nets']['early']))
    a['nets']['sample_boundary'].update(source='slicer.boundary',sinks=['cdr.boundary'])
    cdr['parameters'].update(detector_model='early_late',phase_gain=1/512,
        frequency_gain=1/131072,detector_window_ui=1/16,
        detector_wide_window_ui=1/8,detector_widen_after_ui=64,
        gap_frequency_boost=4.,gap_frequency_boost_after_ui=64,
        holdover_bits=512,holdover_residual_ppm=100.,
        detector_jitter_rms_s=a['cdr_tracking_requirements']['local_aperture_supply_coupling']['timestamp_noise_allocation']['random_rms_target_s'],
        supply_sensitivity_ps_per_mv=a['cdr_tracking_requirements']['local_aperture_supply_coupling']['provisional_target_ps_per_mv'])
    a['blocks']['ctle']['parameters']['pole_s']*=1.2
    return DesignDefinition.from_documents(design.contract,a)


def cdr_window_controls(design):
    """Resolve detector/control behavior from that same circuit snapshot."""
    a=design.architecture;p=a['blocks']['cdr']['parameters']
    if a['blocks']['slicer']['parameters'].get('tracking_sampler_count')!=4:
        raise ValueError('Window controller requires its four-sampler circuit snapshot')
    controls={key:p[key] for key in ('detector_model','phase_gain','frequency_gain','frequency_slope_gain',
        'detector_window_ui','detector_wide_window_ui','detector_widen_after_ui',
        'gap_frequency_boost','gap_frequency_boost_after_ui','holdover_residual_ppm')}
    controls.update(detector_noise_rms_s=p['detector_jitter_rms_s'],holdover_ui=p['holdover_bits'],
        ctle_zero_s=a['blocks']['ctle']['parameters']['zero_s'],
        ctle_pole_s=a['blocks']['ctle']['parameters']['pole_s'],bound_aperture_motion=True)
    return controls


def cdr_full_cycle_screen(contract,architecture,*,aperture_screen=False,observed_bound=False,slope_screen=False,detector_screen=False,window_screen=False,source_seed=9022,source_phase_cycles=0.,initial_conditions=((.35,100.),),design=None,window_residual_ppm=None,window_design=None):
    """Matched full-excursion comparison; no source timing enters the CDR."""
    import numpy as np
    if type(source_seed) is not int or source_seed<0 or not np.isfinite(source_phase_cycles):
        raise ValueError('Nonnegative integer source seed and finite SSC phase required')
    if window_residual_ppm is not None and (not window_screen or
            isinstance(window_residual_ppm,bool) or not np.isfinite(window_residual_ppm) or window_residual_ppm<=0):
        raise ValueError('Positive residual allocation requires the window candidate')
    if window_design is not None and not window_screen:
        raise ValueError("Explicit window design requires the window screen")
    parent_provenance=None
    if window_screen:
        if design is None:design=DesignDefinition.from_documents(contract,architecture)
        elif design.contract!=contract or design.architecture!=architecture:
            raise ValueError('CDR candidate documents conflict with supplied parent')
        parent_provenance=design.provenance()
        design=cdr_window_candidate(design) if window_design is None else window_design
        cdr_window_controls(design)  # Validate the explicit four-sampler topology.
        if window_residual_ppm is not None:
            design=design.hypothetical(reason='Joint residual-frequency/phase budget comparison; gap and quarter-UI gates unchanged',
                changes={'blocks.cdr.parameters.holdover_residual_ppm':window_residual_ppm})
        contract,architecture=design.contract,design.architecture
    env,context=wired_receiver_environment(contract,architecture,design=design)
    if window_screen:context['candidate_parent_provenance']=parent_provenance
    trial,clock=b.reference_payload_environment(env,dict(link_r_ohm=1e-5),False)
    if trial is None:return dict(context,cases=[],clock=clock,status='clock_rejected')
    base=dict(b.wired_shared_impairment(trial),name='full_cycle_comparison',
              ctle_zero_s=200e-12,ctle_pole_s=80e-12,holdover_ui=512)
    count=170000
    bits=np.random.default_rng(source_seed).integers(0,2,count).tolist()
    phase=(np.arange(count)*30e3/2.5e9+source_phase_cycles)%1.
    ppm=-5000.*(1.-abs(2.*phase-1.))
    edges=np.r_[0.,np.cumsum(1./(2.5e9*(1.+ppm*1e-6)))]
    gaps=[(25000,192),(65000,512),(105000,512),(145000,192)]
    rows=[]
    choices=(('transition_fit_256_half_coupling',.08,256,'least_squares',.5),
             ('transition_fit_256_quarter_coupling',.08,256,'least_squares',.25)) if aperture_screen else (
             ('integral',.15,0,'interval',1.),('transition_fit_256',.08,256,'least_squares',1.))
    if observed_bound:choices=(('transition_fit_256_observed_bound',.08,256,'least_squares',.5),
                               ('transition_fit_256_tighter_clock_and_timestamp',.08,256,'least_squares',.25))
    if slope_screen:choices=(('slope_predictor',.06,0,'interval',.25),)
    if detector_screen:choices=(('early_late_slow_integrator',1/256,0,'interval',.25),
                               ('early_late_faster_integrator',1/256,0,'interval',.25),
                               ('early_late_smaller_steps',1/512,0,'interval',.25))
    if window_screen:choices=(('windowed_early_late',architecture['blocks']['cdr']['parameters']['phase_gain'],0,'interval',1.),)
    for name,gain,window,fit,coupling_scale in choices:
        for with_gaps in ((True,) if slope_screen or detector_screen or window_screen else (False,True)):
            pattern=list(bits)
            if with_gaps:
                for start,length in gaps:
                    pattern[start-1:start+length+1]=[1]+[0]*length+[1]
            impairment=dict(base,phase_gain=gain,frequency_gain=.0002,
                detector_noise_rms_s=5e-12,frequency_window_ui=window,
                frequency_average_gain=1.,frequency_fit=fit,
                delay_tones=[dict(t,delay_peak_s=t['delay_peak_s']*coupling_scale) for t in base['delay_tones']])
            if slope_screen:
                # For transition density d=0.5, the small-signal continuous
                # approximation is l^3+d*Kp*l^2+d*Kf*l+d*Ks.
                # These gains give (l+0.01)^3, about4MHz at2.5Gb/s.
                # Discrete updates, actual transitions and saturation still
                # require the causal voltage-domain test below.
                impairment.update(frequency_gain=.0006,frequency_slope_gain=2e-6,
                    detector_noise_rms_s=architecture['cdr_tracking_requirements']['local_aperture_supply_coupling']['timestamp_noise_allocation']['random_rms_target_s'],
                    bound_aperture_motion=True)
            if detector_screen:
                # Two faster candidates retain Kp/Kf=256 bit intervals.
                # A ramp at0.12ppm/UI then suggests roughly31ppm lag in
                # a smoothed local approximation; binary jitter and gaps must
                # still be checked rather than inferred from that estimate.
                frequency_step={'early_late_slow_integrator':1e-6,
                    'early_late_faster_integrator':1/65536,
                    'early_late_smaller_steps':1/131072}[name]
                impairment.update(detector_model='early_late',frequency_gain=frequency_step,
                    detector_noise_rms_s=architecture['cdr_tracking_requirements']['local_aperture_supply_coupling']['timestamp_noise_allocation']['random_rms_target_s'],
                    bound_aperture_motion=True)
            if window_screen:
                impairment.update(cdr_window_controls(design))
            tail_budget=None
            if observed_bound:
                from wired_envelope import timestamp_tail_budget
                allocation=architecture['cdr_tracking_requirements']['local_aperture_supply_coupling']['timestamp_noise_allocation']
                impairment.update(edge_time_bound_s=50e-12 if coupling_scale==.5 else 25e-12,bound_aperture_motion=True)
                if coupling_scale==.25:impairment['detector_noise_rms_s']=allocation['random_rms_target_s']
                tail_budget=timestamp_tail_budget(bound_s=impairment['edge_time_bound_s'],
                    deterministic_s=allocation['deterministic_allowance_s'],
                    noise_rms_s=impairment['detector_noise_rms_s'],
                    tail_probability=allocation['exceedance_probability_per_observation'])
            result=b.causal_receiver_envelope(timing_scenarios=[impairment],
                channel_cases=((2.7e-12,100e-12),),source_bits=pattern,
                source_edges_s=edges,initial_conditions=initial_conditions)
            tracking_target=architecture['cdr_traffic_requirements']['selected_budget']['qualified_residual_frequency_error_target_ppm']
            checks=dict(
                tracking_frequency_target=bool(result['cases']) and all(c['heldout_free_run_residual_abs_ppm_quantiles'][-1]<=tracking_target for c in result['cases']),
                decoded_bits=bool(result['cases']) and all(c['heldout_errors']==0 for c in result['cases']),
                receive_policy=bool(result['cases']) and all(c['heldout_policy_valid_fraction']==1. and c['qualification_losses']==0 for c in result['cases']),
                residual_bound=bool(result['cases']) and all(c['heldout_instantaneous_residual_bound_violations']==0 for c in result['cases']),
                sampled_phase_budget=bool(result['cases']) and all(c['heldout_qualified_fraction']==1. and c['measured_gap_phase']['scored_samples_outside_quarter_ui']==0 for c in result['cases']))
            rows.append(dict(candidate=name,checks=checks,tracking_frequency_target_ppm=tracking_target,conditional_acceptance=all(checks.values()),with_gaps=with_gaps,timestamp_tail_budget=tail_budget,detector_noise_rms_s=impairment['detector_noise_rms_s'],edge_time_bound_s=impairment.get("edge_time_bound_s"),aperture_coupling_scale=coupling_scale,
                local_supply_delay_sensitivity_s_per_v=trial['cdr_supply_delay_parameters']['supply_sensitivity_ps_per_mv']*1e-9*coupling_scale,
                inserted_gaps=[dict(start_bit=i,length_ui=n) for i,n in gaps] if with_gaps else [],
                phase_gain=gain,frequency_window_ui=window,frequency_slope_gain=impairment.get('frequency_slope_gain',0.),
                diagnostic_intervention=dict(
                    reason='Fixed loop/channel requirement hypotheses; not a resolved selectable chip configuration',
                    loop_parameters={key:impairment[key] for key in (
                        'ctle_zero_s','ctle_pole_s','holdover_ui','phase_gain','frequency_gain',
                        'detector_noise_rms_s','frequency_window_ui','frequency_average_gain','frequency_fit')},
                    channel_cap_f=2.7e-12,channel_tau_s=100e-12,
                    local_supply_delay_coupling_scale=coupling_scale),result=result))
    return dict(context,cases=rows,clock=clock,source_bits=count,source_seed=source_seed,source_phase_cycles=source_phase_cycles,source_duration_s=float(edges[-1]),
        source_downspread_ppm=5000.,modulation_hz_nominal=30000.,
        model_role='cdr_requirement_comparison',
        detector_noise_scope="Per-case values; improved observed-bound candidate reads normative noise allocation",declared_holdover_residual_ppm=architecture['blocks']['cdr']['parameters']['holdover_residual_ppm'] if window_screen else 50.,
        aperture_screen=aperture_screen,observed_bound=observed_bound,slope_screen=slope_screen,detector_screen=detector_screen,window_screen=window_screen,
        window_controls=cdr_window_controls(design) if window_screen else None,
        window_scope='Four-sampler behavioral requirement comparison. Actual window sizes, equalizer pole, residual allocation and loop gains are recorded in window_controls; actual supply coupling is recorded per case. Unchanged 512UI gap and quarter-UI acceptance limits. Window misses preserve propagated uncertainty. No source timing enters feedback. Phase-actuator latency/glitch-free switching, cold acquisition, physical noise tails, area/current and fabrication compatibility remain unqualified.',
        detector_scope='Early/late experiment uses three voltage samples only. Gains are explicit hypotheses; no phase magnitude observer is implemented, so timing qualification must stay false even if bits decode. No timestamp oracle enters feedback.',
        slope_scope='Optional third-order predictor with explicit quarter local coupling and shared detector-noise target. Existing50ppm residual and0.25UI phase gates unchanged; predictor slew is charged in holdover. No proven physical tuning, cost, bounded detector tail or selected-hardware promotion.', 
        observed_bound_scope="Explicit50ps/half-coupling control versus25ps/quarter-coupling improvement. Timestamp bounds are not derived from5ps Gaussian RMS or physically guaranteed. Same SSC/channel/phase limit and causal movement accounting; improved candidate reads2ps RMS target with explicit Gaussian tail budget, control retains5ps RMS. Physical tail coverage and implementation cost remain unqualified.",
        coupling_scope='Only local supply-to-aperture delay tones scaled; rail waveform, signal amplitude, detector noise and physical allocations unchanged. Each loop reruns causally. No current/area cost or physical attainment inferred.',
        scope='Two nominal-bit-time triangular SSC cycles, identical inventory/package/channel, '
        'initial phase/offset and noise seed. Compare the explicitly recorded loop/coupling cases '
        'with continuous data and192/512UI gaps in both ramp directions. Source edge times '
        'drive only channel stimulus and independent scoring. Unchanged qualification/phase '
        'limits; no physical detector/counter cost, jitter-mask, BER or protocol qualification.')


def converter_timing_variants(design):
    """Circuit experiments retain their own identities and parameter ownership."""
    stress={
        'blocks.refbuf.parameters.output_r_ohm':100.,
        'blocks.refbuf.parameters.source_limit_a':.5e-3,
        'model_assumptions.paired_sar.parameters.comparator_noise_rms_v':.002}
    for lane in ('adc_i','adc_q'):
        stress[f'blocks.{lane}.parameters.diagnostic_input_cap_budget_f']=150e-15
        stress[f'blocks.{lane}.parameters.diagnostic_series_resistance_budget_ohm']=300.
    for name,loading in (('selected',design),('combined_loading_stress',design.hypothetical(
            reason='Simultaneous converter switch loading, reference impedance/current and noise stress',changes=stress))):
        nominal=loading.architecture['model_assumptions']['paired_sar_comparator']['parameters']['tau_s']
        for tau in dict.fromkeys((nominal,100e-12,150e-12)):
            variant=loading if tau==nominal else loading.hypothetical(
                reason='Comparator regeneration timing uncertainty probe',
                changes={'model_assumptions.paired_sar_comparator.parameters.tau_s':tau})
            yield name,variant


def converter_timing_screen(contract,architecture,*,design=None):
    """Cross explicit circuit hypotheses using each variant's shared model."""
    from converter_dynamics import parameters_from_inventory,tone_precision
    from dataclasses import asdict
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('Converter documents conflict with supplied design snapshot')
    rows=[]
    for name,variant in converter_timing_variants(design):
        a=variant.architecture
        config=variant.configure(engine='rf',direction='rx',reference_hz=2.5e9,
            sample_divider=64,pga_gain_db=max(a['blocks']['pga_i']['parameters']['gain_db']))
        scenario=Scenario()
        environment=b.configured_environment(config,scenario)
        trial,clock=b.reference_payload_environment(environment,dict(link_r_ohm=1e-5),False)
        parameters=parameters_from_inventory(a)
        comparator=a['model_assumptions']['paired_sar_comparator']['parameters']
        row=dict(design_provenance=variant.provenance(),resolved_configuration=config.record(),
            scenario_overrides=scenario.record(),loading=name,parameters=asdict(parameters),
            comparator=comparator,clock=clock)
        if trial is None:
            row.update(rejected='Common converter clock rejected',conditional_pass=False)
            rows.append(row);continue
        try:
            row['result']=tone_precision(trial,parameters,count=512,bin_number=127,
                shared_clock_feedback=True,comparator_model=comparator)
            result=row['result'];converter=result['converter']
            row['acceptance']=dict(
                precision_margin_bits=min(value-a['blocks'][name]['parameters']['enob_target']
                    for name,value in zip(('adc_i','adc_q'),result['fullscale_normalized_enob'],strict=True)),
                conversion_margin_s=converter['actual_completion_margin_s'],
                cycle_margin_s=converter['schedule_margin_s'],
                feedback_converged=result['numerical_feedback_converged'])
            row['conditional_pass']=bool(row['acceptance']['precision_margin_bits']>=0
                and row['acceptance']['conversion_margin_s']>=0
                and row['acceptance']['cycle_margin_s']>=0
                and row['acceptance']['feedback_converged'])
        except ValueError as error:
            row['rejected']=str(error);row['conditional_pass']=False
        rows.append(row)
    return dict(design_provenance=design.provenance(),cases=rows,
        scope='Each circuit variant resolves its RF inventory, selected package and delivered clock independently. '
        'Reference-current feedback and selected cycle guard; assigned comparator regeneration crossed '
        'with simultaneous switch loading, reference impedance/current and comparator noise. '
        'Finite tone sample; no rare-event bound, diagnostic reference-source switching, mismatch, '
        'kickback, physical comparator supply dependence or protocol qualification.')


def common_envelope_screen(contract,architecture,*,design=None):
    """Same package catalog and inventory currents for both payload engines.

    This first layer rejects incompatible delivered clocks and converter cycle
    assumptions before packet work. Clock acceptance does not imply payload pass.
    """
    from converter_dynamics import parameters_from_inventory,tone_precision
    import numpy as np
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('Common-envelope documents conflict with supplied design snapshot')
    rows=[]
    for label,inductance,esl in b.network_cases(design):
        for mode in ('rf','wire'):
            settings=dict(engine=mode,direction='rx',reference_hz=2.5e9)
            if mode=='rf':settings.update(sample_divider=64,pga_gain_db=max(architecture['blocks']['pga_i']['parameters']['gain_db']))
            else:settings['host_divider']=8
            config=design.configure(**settings)
            scenario=Scenario()
            if label!=b.BASELINE_PACKAGE_CASE:
                scenario=scenario.override(reason='Common-envelope package uncertainty',
                    package_return_inductance_h=inductance,die_decoupling_esl_h=esl)
            e=b.configured_environment(config,scenario)
            context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
                         scenario_overrides=scenario.record())
            trial,clock=b.reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
            p=parameters_from_inventory(architecture)
            cycle=p.acquisition_s+sum(p.bit_durations_s)+p.reset_control_s
            payload={}
            if trial is not None and mode=='rf':
                def converter_case(name,variant,asynchronous):
                    variant_config=variant.configure(**settings)
                    variant_env=b.configured_environment(variant_config,scenario)
                    loaded,variant_clock=b.reference_payload_environment(variant_env,dict(link_r_ohm=1e-5),False)
                    parameters=parameters_from_inventory(variant.architecture)
                    comparator=variant.architecture['model_assumptions']['paired_sar_comparator']['parameters'] if asynchronous else None
                    row=dict(name=name,design_provenance=variant.provenance(),
                        resolved_configuration=variant_config.record(),scenario_overrides=scenario.record(),
                        comparator=comparator,clock=variant_clock,
                        comparator_scope='Shared regeneration law' if asynchronous else 'Fixed-duration SAR primitive simplification')
                    if loaded is None:return dict(row,rejected='Variant clock rejected')
                    try:
                        row['result']=tone_precision(loaded,parameters,count=512,bin_number=127,
                            shared_clock_feedback=True,comparator_model=comparator)
                    except ValueError as error:row['rejected']=str(error)
                    return row
                variants=list(converter_timing_variants(design))
                nominal_tau=architecture['model_assumptions']['paired_sar_comparator']['parameters']['tau_s']
                payload['converter_cases']=[converter_case(name,variant,False) for name,variant in variants
                    if variant.architecture['model_assumptions']['paired_sar_comparator']['parameters']['tau_s']==nominal_tau]
                if label==b.BASELINE_PACKAGE_CASE:
                    payload['asynchronous_converter_cases']=[converter_case(name,variant,True)
                        for name,variant in variants if name=='selected']
            elif trial is not None:
                receiver_inputs=b.baseline_wired_receiver_inputs(trial,label='shared_inventory')
                impairment=receiver_inputs['timing_scenario']
                payload['receiver_inventory']=receiver_inputs['receiver_inventory']
                payload['probe_assumptions']=receiver_inputs['probe_assumptions']
                default_holdover=receiver_inputs['receiver_inventory']['holdover_ui']
                bits=np.random.default_rng(9021).integers(0,2,2600).tolist()
                payload['shared_pad']=shared_pad_envelope(clock['ledger']['local_payload_clock_core_rail_v'],
                    usb_supply=usb_inventory_supply(contract,architecture,return_l=inductance,die_esl=esl,design=design),architecture=architecture,design=design)
                payload['cdr_cases']=[]
                for name,pattern,holdover in (('continuous',bits,default_holdover),
                        ('transition_drought_default',bits[:1400]+[0]*192+bits[1592:],default_holdover),
                        ('transition_drought_configured',bits[:1400]+[0]*192+bits[1592:],512)):
                    result=b.causal_receiver_envelope(timing_scenarios=[dict(impairment,holdover_ui=holdover)],
                        channel_cases=(receiver_inputs['channel_case'],),source_bits=pattern)
                    payload['cdr_cases'].append(dict(name=name,holdover_ui=holdover,
                        holdover_override=holdover!=default_holdover,result=result))
                if label=='lower_return_probe':
                    # Two nominal 30 kHz triangular downspread cycles. Source
                    # edge times drive the voltage channel, never CDR control.
                    count=170000
                    source_bits=np.random.default_rng(9022).integers(0,2,count).tolist()
                    phase=(np.arange(count)*30e3/2.5e9)%1.
                    ppm=-5000.*(1.-abs(2.*phase-1.))
                    edges=np.r_[0.,np.cumsum(1./(2.5e9*(1.+ppm*1e-6)))]
                    result=b.causal_receiver_envelope(
                        timing_scenarios=[impairment],channel_cases=(receiver_inputs['channel_case'],),
                        source_bits=source_bits,source_edges_s=edges,
                        initial_conditions=((.35,100.),))
                    payload['cdr_cases'].append(dict(name='two_cycle_downspread',result=result,
                        holdover_ui=default_holdover,holdover_override=False,
                        source_downspread_ppm=5000.,modulation_hz_nominal=30000.,
                        source_duration_s=float(edges[-1]),
                        scope='One initial condition; triangular modulation indexed by nominal source-bit time. '
                        'Two cycles with shared supply/aperture tones, finite channel and causal CDR; '
                        'not a full jitter-tolerance mask or SSC interoperability qualification.'))
                    gap_pattern=list(source_bits)
                    gaps=[(25000,192),(65000,512),(105000,512),(145000,192)]
                    for begin,length in gaps:
                        gap_pattern[begin:begin+length]=[0]*length
                        # Bound the advertised run: random neighboring zeros
                        # otherwise turn a512UI test into an over-limit516UI test.
                        gap_pattern[begin-1]=gap_pattern[begin+length]=1
                    gap_result=b.causal_receiver_envelope(
                        timing_scenarios=[dict(impairment,holdover_ui=512)],
                        channel_cases=(receiver_inputs['channel_case'],),source_bits=gap_pattern,
                        source_edges_s=edges,initial_conditions=((.35,100.),))
                    payload['cdr_cases'].append(dict(name='downspread_with_transition_gaps',
                        holdover_ui=512,holdover_override=512!=default_holdover,
                        result=gap_result,inserted_gaps=[dict(start_bit=i,length_ui=n) for i,n in gaps],
                        source_downspread_ppm=5000.,modulation_hz_nominal=30000.,
                        scope='Exact192/512UI runs bounded by opposite-level bits on both SSC ramp directions; one initial condition and unchanged declared50ppm admission bound. Independent measured gap drift can reject a falsely qualified holdover.'))


            rows.append(dict(context,package=label,mode=mode,
                inventory_current_ma=e['inventory_current_report']['total_ma'],
                ledger=clock['ledger'],clock_status=clock['status'],
                converter_timing=[dict(unmodeled_cycle_uncertainty_s=u,
                    sample_period_s=1/config.sample_hz,
                    remaining_s=1/config.sample_hz-cycle-u,admissible=1/config.sample_hz>=cycle+u)
                    for u in (0.,.2e-9,.6e-9,1e-9)] if mode=='rf' else None,
                payload=payload,payload_qualified=False))
    return dict(design_provenance=design.provenance(),cases=rows,host_output_capacitance_f=contract['physical_services']['host_output']['full_rate_external_load_target_f'],
        host_load_scope='Selected external board load propagated through host spectrum and partitioned delivered-clock network; internal output-cell charge remains assigned separately',
        selected_converter_guard_s=p.unmodeled_cycle_uncertainty_s,
        selected_converter_diagnostic_cap_f=p.diagnostic_input_cap_f,
        selected_converter_diagnostic_series_ohm=p.diagnostic_series_resistance_ohm,
        scope='Shared current/package/clock environment drives paired SAR/reference feedback and causal wired CDR with transition drought. Short sine/NRZ diagnostics plus two-cycle SSC on the lower-return case; not RF packets, SDI patterns, a complete SSC tolerance mask or integrated lifecycle qualification. Connected shared-pad DC/transfer/transition diagnostics are included; physical protection and full system recovery remain open.')


def packet_environment(contract,architecture,*,gain_db,wanted_dbm,blocker_dbm=None,reference_hz=2.426e9,design=None):
    """Shared RF packet seed; channel and gain are settings, levels are stimuli."""
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('Packet documents conflict with supplied design snapshot')
    config=design.configure(engine='rf',direction='rx',reference_hz=reference_hz,
                            sample_divider=64,pga_gain_db=gain_db)
    scenario=Scenario(wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm)
    environment=b.configured_environment(config,scenario)
    return environment,dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),scenario_stimuli=scenario.stimulus_record())


def common_rf_packet_screen(contract,architecture,*,filter_family="rx_finite_zero",design=None):
    """Real RX packet on the same physical/current catalog, at its RF channel."""
    from converter_dynamics import parameters_from_inventory
    from selected_rf import minimum_envelope_oversample
    label=b.BASELINE_PACKAGE_CASE
    carrier=2.426e9
    e,context=packet_environment(contract,architecture,gain_db=39.,wanted_dbm=-80.,
                                 blocker_dbm=-50.,design=design)
    trial,clock=b.reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
    result=dict(context,package=label,carrier_hz=carrier,clock=clock,
        inventory_current_ma=e['inventory_current_report']['total_ma'],
        host_output_capacitance_f=contract['physical_services']['host_output']['full_rate_external_load_target_f'])
    if trial is None:return dict(result,status='clock_rejected')
    steps=max(256,minimum_envelope_oversample(trial,sample_hz=carrier/64,guard_hz=3.1e6))
    options=dict(lo_divider=64,noise_figure_db=architecture['blocks']['lna']['parameters']['noise_figure_db'],
        input_iip3_dbm=architecture['blocks']['lna']['parameters']['iip3_dbm'],
        rx_cutoff_hz=.5e6,rx_filter_family=filter_family,converter_bits=architecture['blocks']['adc_i']['parameters']['native_bits'],
        initial_gain_db=39.,maximum_gain_db=max(architecture['blocks']['pga_i']['parameters']['gain_db']),
        gain_codes_db=architecture['blocks']['pga_i']['parameters']['gain_db'],
        aperture_rms_s=trial['adc_noise_parameters']['aperture_rms_s'],dynamic_rail=True,sar_parameters=parameters_from_inventory(architecture),
        comparator_model=architecture['model_assumptions']['paired_sar_comparator']['parameters'],mixer_substeps=steps)
    stimulus=dict(seed=81,wanted_dbm=-80.,blocker_dbm=-50.,blocker_modulation='gfsk_prbs15')
    try:
        received,_=b.coupled_scan_request(trial,contract,rx_options=options,stimulus=stimulus,
            progress=lambda x:print('Common RF packet feedback',x['iteration'],x['correct_request'],flush=True))
        result.update(receiver=received,status='conditional_packet_decode' if received['correct_request'] and
            received['reference_feedback']['numerical_feedback_converged'] else 'packet_or_feedback_failed')
    except ValueError as error:
        result.update(status='rejected',reason=str(error))
    return dict(result,stimulus=stimulus,mixer_substeps=steps,filter_family=filter_family,
        scope='Channel38 BLE request through RF noise/nonlinearity, selected finite-zero filter, received-code AGC, '
        'asynchronous SAR and reference-to-clock feedback. Same inventory current, host load and package catalog '
        'as common converter/wired cases; actual RF channel changes clock frequencies. One seed and blocker point; '
        'not sensitivity/PER qualification, RF TX, Wi-Fi, runtime calibration or the complete chip lifecycle.')


def common_wideband_packet_screen(contract,architecture,*,wanted_dbm=-85.,design=None):
    """Wideband acquisition control on selected inventory, not HE compliance."""
    from converter_dynamics import parameters_from_inventory
    from wideband_packet import run_acquisition_case
    label=b.BASELINE_PACKAGE_CASE
    carrier=2.426e9
    environment,context=packet_environment(contract,architecture,
        gain_db=max(architecture['blocks']['pga_i']['parameters']['gain_db']),
        wanted_dbm=wanted_dbm,blocker_dbm=-30.,design=design)
    trial,clock=b.reference_payload_environment(environment,dict(link_r_ohm=1e-5),False)
    result=dict(context,package=label,carrier_hz=carrier,clock=clock,
        inventory_current_ma=environment['inventory_current_report']['total_ma'])
    if trial is None:return dict(result,status='clock_rejected')
    gain_codes=architecture['blocks']['pga_i']['parameters']['gain_db']
    options=dict(start_sample=137,carrier_offset_hz=-120e3,
        oversample=max(256,b.minimum_envelope_oversample(trial)),payload_bytes=16,
        wanted_dbm=wanted_dbm,blocker_dbm=-30.,gain_db=max(gain_codes),gain_codes_db=gain_codes,
        noise_figure_db=architecture["blocks"]["lna"]["parameters"]["noise_figure_db"],
        input_iip3_dbm=architecture["blocks"]["lna"]["parameters"]["iip3_dbm"],
        sar_parameters=parameters_from_inventory(architecture),
        comparator_model=architecture['model_assumptions']['paired_sar_comparator']['parameters'])
    try:
        receiver=run_acquisition_case(trial,431,**options)
        result.update(receiver=receiver,status='conditional_wideband_decode' if
            receiver['payload_correct'] and receiver['analog']['numerical_feedback_converged']
            else 'packet_or_feedback_failed')
    except ValueError as error:result.update(status='rejected',reason=str(error))
    return dict(result,wanted_dbm=options['wanted_dbm'],gain_db=options['gain_db'],
        gain_codes_db=gain_codes,mixer_oversample=options['oversample'],
        scope='Common inventory and selected gain/diagnostic loading/asynchronous SAR. Legacy acquisition followed by diagnostic coded HE20 DATA; fixed legal gain, one weak wanted/blocker point. No HE signaling, HE-LTF, AGC, PER or Wi-Fi interoperability qualification.')


def rf_output_load_screen(architecture,baseline):
    """Fast narrowband extrapolation of a recorded waveform, not a new TX run."""
    import math
    import numpy as np
    from selected_rf import rf_pad_transfer
    driver=architecture['blocks']['rfdriver']['parameters']
    pad=architecture['blocks']['rftxpad']['parameters']
    architecture_hash=hashlib.sha256(json.dumps(architecture,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    provenance=baseline.get('design_provenance')
    if provenance is not None and provenance.get('documents',{}).get('spec/analog-architecture.json')!=architecture_hash:
        raise ValueError('RF output baseline and architecture provenance conflict')
    tx=baseline['transmitter'];carrier=baseline['carrier_hz']
    frequency=carrier+np.linspace(-10e6,10e6,65)
    nominal=tx['nominal_gain'];power=tx['loaded_average_active_power_w']
    peak=tx['electrical']['peak_open_v']
    source=driver['source_r_ohm_differential'];load=driver['load_ohm_differential']
    original_transfer=load/(source+tx.get('pad_series_ohm',0.)+load)
    gain_min,gain_max=driver['gain_range'];step=(gain_max-gain_min)/(2**driver['gain_bits']-1)
    target=1e-3*10**(driver['target_mean_power_dbm']/10)
    rows=[]
    matching=1/((2*math.pi*carrier)**2*8e-9)
    for inductance,match in ((0.,None),(1e-9,None),(4e-9,None),(8e-9,None),(8e-9,matching)):
        transfer=rf_pad_transfer(frequency,driver_r_ohm=source,
            pad_series_ohm=2*pad['series_r_ohm_per_leg'],bond_series_ohm=.4,
            bond_loop_h=inductance,differential_cap_f=pad['capacitance_f_per_leg']/2,load_ohm=load,series_match_f=match)
        ratio=abs(transfer['load_voltage'])/original_transfer
        worst_power=power*float(min(ratio))**2
        required=nominal*math.sqrt(target/worst_power)
        candidate=gain_min+max(0,math.ceil((required-gain_min)/step))*step
        fits=candidate<=gain_max+1e-12
        scale=candidate/nominal
        rows.append(dict(signal_loop_h=inductance,external_series_match_f=match,
            load_transfer_magnitude_interval=[float(min(abs(transfer['load_voltage']))),float(max(abs(transfer['load_voltage'])))],
            estimated_power_dbm_at_existing_gain=10*math.log10(worst_power/1e-3),
            required_gain_continuous=required,required_gain_quantized=candidate,
            gain_range_fits=fits,
            estimated_driver_peak_current_a=peak*scale*float(max(abs(transfer['driver_current']))),
            estimated_open_peak_v=peak*scale,
            assigned_current_and_headroom_fit=bool(fits and
                peak*scale*max(abs(transfer['driver_current']))<=driver['bias_current_a'] and
                peak*scale<=tx['electrical']['allowed_open_peak_v'])))
    # Assigned sensitivity grid, not inferred foundry/package distributions.
    # Per-board trim uses measured loop L at one fixed band-center frequency;
    # it does not retune the matching capacitor on each radio channel.
    from itertools import product
    tolerances=[];center=2.45e9
    for policy,spread in (('fixed_capacitor',.10),('per_board_trim',.02)):
        trials=[]
        for inductance,cap,bond_r,error,rf in product(
                (6.4e-9,8e-9,9.6e-9),(.4e-12,.5e-12,.6e-12),
                (.2,.6,1.),(-spread,0.,spread),(2.4e9,2.45e9,2.5e9)):
            nominal_l=8e-9 if policy=='fixed_capacitor' else inductance
            match=(1+error)/((2*math.pi*center)**2*nominal_l)
            t=rf_pad_transfer(rf+np.linspace(-10e6,10e6,65),driver_r_ohm=source,
                pad_series_ohm=2*pad['series_r_ohm_per_leg'],bond_series_ohm=bond_r,
                bond_loop_h=inductance,differential_cap_f=cap,load_ohm=load,series_match_f=match)
            predicted=power*(float(min(abs(t['load_voltage'])))/original_transfer)**2
            required=nominal*math.sqrt(target/predicted)
            code=gain_min+max(0,math.ceil((required-gain_min)/step))*step
            voltage=peak*code/nominal
            current=voltage*float(max(abs(t['driver_current'])))
            trials.append(dict(signal_loop_h=inductance,differential_pad_cap_f=cap,
                series_loss_ohm=bond_r,matching_fractional_error=error,carrier_hz=rf,
                series_match_f=match,required_gain=code,
                estimated_open_peak_v=voltage,estimated_driver_peak_current_a=current,
                admitted=bool(code<=gain_max+1e-12 and voltage<=tx['electrical']['allowed_open_peak_v']
                    and current<=driver['bias_current_a'])))
        tolerances.append(dict(policy=policy,sensitivity_points=len(trials),
            admitted_points=sum(t['admitted'] for t in trials),
            required_gain_interval=[min(t['required_gain'] for t in trials),max(t['required_gain'] for t in trials)],
            worst_gain_case=max(trials,key=lambda t:t['required_gain']),
            worst_current_case=max(trials,key=lambda t:t['estimated_driver_peak_current_a'])))
    return dict(cases=rows,tolerance_screen=dict(cases=tolerances,match_center_hz=center,
        scope='Assigned6.4–9.6nH signal-loop,0.4–0.6pF differential pad,0.2–1ohm series loss and2.4–2.5GHz grid. Fixed matching assumes±10percent capacitance error; per-board trim assumes actual loop measurement plus±2percent residual tuning error, with one fixed capacitor across the band. Baseline TX waveform/rail/clock held fixed: not a common-envelope channel sweep, statistical yield, continuous extrema proof or demonstrated calibration.'),carrier_hz=carrier,frequency_interval_hz=[float(frequency[0]),float(frequency[-1])],
        differential_cap_f=pad['capacitance_f_per_leg']/2,signal_bond_resistance_ohm=.4,
        input_baseline_context={key:deepcopy(baseline[key]) for key in (
            'design_provenance','resolved_configuration','scenario_overrides',
            'scenario_assumptions','operating_conditions') if key in baseline},
        input_scope='shared_design_transmitter' if provenance is not None else 'unbound_transmitter_fixture',
        architecture_sha256=architecture_hash,
        baseline_input_rms_codes=tx['input_rms_codes'],baseline_sources_sha256=deepcopy(baseline['sources_sha256']),
        baseline_record_sha256=hashlib.sha256(json.dumps(baseline,sort_keys=True).encode()).hexdigest(),
        status='conditional_narrowband_load_screen',
        scope='Lumped source-R/pad-C/signal-bond-RL/load ladder. Signal inductances0/1/4/8nH and0.4ohm bond loop are hypotheses, independent of supply-return inductance. The matched8nH case uses an ideal external series capacitor resonant at the carrier; tolerance/ESR/self-resonance and board parasitics are not qualified. Frequency samples bound only this sampled wanted band. Recorded waveform power/crest are extrapolated with near-flat linear transfer; no transient/sideband waveform replay, clipping feedback, changed gain noise, reactive device compliance or standards qualification.')


def five_pole_tx_candidate(design):
    """Resolve the selected five-pole design; extend legacy three-pole fixtures once."""
    a=design.architecture;c=design.contract
    if all(a['blocks'][name]['parameters']['order']==5 for name in ('txfilter_i','txfilter_q')):
        from selected_lifecycle import lifecycle_tx_filter
        lifecycle_tx_filter(design)
        return design
    allocation=a['rf_interoperability']['external_frontend']['tx_filter_candidate_resource_screen']
    growth=allocation['area_growth_um2']
    for name in ('txfilter_i','txfilter_q'):
        block=a['blocks'][name]
        if block['parameters']['order']!=3:
            raise ValueError('Five-pole candidate requires a three-pole parent')
        parameters=block['parameters']
        parameters.pop('default_q')
        parameters.update(order=5,topology='differential active-RC two biquads plus real pole',
            default_response='Butterworth',stage_q=[.6180339887498948,1.618033988749895])
        parameters['cutoff_hz'][1]=12e6
        block['resource_allocation']['area_ceiling_um2']+=growth/2
        for mode in ('rf_rx','rf_tx'):
            block['resource_allocation']['current_budget_ma'][mode]=allocation['per_filter_current_ceiling_ma']
    c['area_um2']['rf']+=growth;c['area_um2']['reserve']-=growth
    a['area_budget_um2']=dict(c['area_um2'])
    if c['area_um2']['reserve']<a['resource_totals']['area_used_um2']['reserve']:
        raise ValueError('Candidate consumes allocated power-distribution area')
    a['resource_totals']['area_used_um2']['rf']+=growth
    for mode in a['resource_totals']['current_ma']:
        a['resource_totals']['current_ma'][mode]=sum(block['resource_allocation']['current_budget_ma'][mode] for block in a['blocks'].values())
    return DesignDefinition.from_documents(c,a)


def rf_rejection_candidate(design):
    """Joint inverse-performance target; rejection implementation cost is open."""
    candidate=five_pole_tx_candidate(design)
    c=candidate.contract;a=candidate.architecture
    clock=c['physical_services']['external_clock_input']
    clock['input_model']['mismatch']=.02
    clock['input_model']['cm_gain']=-.01
    clock['supply_sensitivity_ps_per_mv']=.0025
    a['blocks']['rfdriver']['parameters']['supply_gain_model']['high_frequency_elasticity']=.02
    return DesignDefinition.from_documents(c,a)


def tx_clock_component_screen(design):
    """Diagnose delivered phase contributors without improving any clock input."""
    import numpy as np
    from selected_rf import DeliveredClock,PeriodicEdgePhase
    from oscillator_noise import PhaseNoise
    config=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64)
    raw=b.configured_environment(config,Scenario())
    environment,acceptance=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
    result=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),clock_acceptance=acceptance,complete=False)
    if environment is None:return dict(result,status='clock_rejected')
    clock=DeliveredClock(environment)
    input_clock=PeriodicEdgePhase(dict(environment['periodic_clock'],
        edges_s=environment['reference_threshold']['input_edges_s']))
    rows=[]
    for rate in (5.12e9,10.24e9):
        times=2e-6+np.arange(round(25e-6*rate))/rate
        source=PhaseNoise(tuple(environment['phase_components']['source'])).phase(times)
        input_noise=PhaseNoise(tuple(environment['phase_components']['input'])).phase(times)
        total=clock.phase(times)
        loaded_input=input_clock.phase(times)
        downstream=total-source-input_noise-loaded_input
        components=dict(source=source,input_noise=input_noise,loaded_input_edges=loaded_input,
            downstream_distribution=downstream,loaded_edge_and_distribution=loaded_input+downstream,total=total)
        w=np.hanning(len(times));frequencies=abs(np.fft.fftfreq(len(times),1/rate))
        scores={}
        for name,phase in components.items():
            centered=phase-np.mean(phase)
            spectrum=abs(np.fft.fft(centered*w))**2/(len(times)*np.sum(w*w))
            scores[name]=dict(mean_phase_rad=float(np.mean(phase)),
                rms_rad=float(np.sqrt(np.mean(centered**2))),
                above_50mhz_windowed_rms_rad=float(np.sqrt(np.sum(spectrum[frequencies>=50e6]))))
        rows.append(dict(sample_rate_hz=rate,duration_s=25e-6,components=scores,
            summation_residual_rad=float(np.max(abs(total-source-input_noise-components['loaded_edge_and_distribution'])))))
    return dict(result,cases=rows,status='component_diagnostic',
        scope='Current external-clock TX package model at2.426GHz. Source/input assigned tones, pre-distribution threshold edges, and downstream-minus-input phase trajectories separated. Difference is an aligned phase decomposition, not independent random variance. Centered phase, same25us window and two numerical rates; not independent stochastic variances, RF power, phase-noise density, BER or measured clock quality. Edge interpolation reconstructs phase between carrier crossings; higher-frequency physical information is not recovered by oversampling it.')


def common_tx_screen(contract,architecture,*,input_rms_codes=180.,signal_loop_nh=None,series_match_pf=None,driver_gain=None,design=None,impairment_capture=None,fpga_preemphasis=None):
    """Transmit quality and watts on the same inventory/clock/package catalog."""
    import math
    from selected_rf import wideband_transmit
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('TX documents conflict with supplied design snapshot')
    label=b.BASELINE_PACKAGE_CASE
    carrier=2.426e9
    config=design.configure(engine='rf',direction='tx',reference_hz=carrier,sample_divider=64,tx_gain=driver_gain)
    scenario=Scenario()
    driver=architecture['blocks']['rfdriver']['parameters']
    cutoff=max(architecture['blocks']['txfilter_i']['parameters']['cutoff_hz'])
    gain=config.resolved_tx_gain
    if series_match_pf is not None and signal_loop_nh is None:
        raise ValueError('Matching requires explicit RF signal-loop network')
    network=None if signal_loop_nh is None else dict(bond_series_ohm=.4,
        bond_loop_h=signal_loop_nh*1e-9,
        differential_cap_f=architecture['blocks']['rftxpad']['parameters']['capacitance_f_per_leg']/2,
        series_match_f=None if series_match_pf is None else series_match_pf*1e-12)
    environment=b.configured_environment(config,scenario)
    trial,clock=b.reference_payload_environment(environment,dict(link_r_ohm=1e-5),False)
    result=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),stimulus=dict(input_rms_codes=input_rms_codes),
        selected_controls=dict(driver_gain_requested=driver_gain,driver_gain_resolved=gain,
                               reconstruction_cutoff_hz=cutoff),
        rf_load_hypothesis=network,package=label,carrier_hz=carrier,clock=clock,
        inventory_current_ma=environment['inventory_current_report']['total_ma'])
    if trial is None:return dict(result,status='clock_rejected')
    transmitter=wideband_transmit(trial,oversample=max(256,b.minimum_envelope_oversample(trial)),
        cutoff_hz=cutoff,input_rms_codes=input_rms_codes,nominal_gain=gain,rf_load=network,impairment_capture=impairment_capture,fpga_preemphasis=fpga_preemphasis,
        pad_series_ohm=2*architecture['blocks']['rftxpad']['parameters']['series_r_ohm_per_leg'])
    dbm=10*math.log10(transmitter['loaded_average_active_power_w']/1e-3)
    target=driver['target_mean_power_dbm']
    swing=architecture['blocks']['txmix_i']['parameters']['maximum_input_complex_peak_v']
    return dict(result,transmitter=transmitter,input_rms_codes=input_rms_codes,loaded_mean_power_dbm=dbm,target_mean_power_dbm=target,
        power_target_met=dbm>=target,mixer_input_limit_v=swing,
        mixer_input_limit_met=transmitter['mixer_input_complex_peak_v']<=swing,
        status='conditional_tx_screen',
        scope='Shared reconstruction cutoff and inventory driver gain; explicit complex RMS transport-code waveform request. RF TX current inventory with the same host-load and package assumptions as common RX. Warm fixed bias, shared DAC ENOB assumption and assigned driver nonlinearity. Optional reactive load is a causal lumped envelope network with ideal matching, not a qualified package. No signal-dependent current feedback, nonlinear reactive current limiting, external PA/filter or standards-valid emission mask. This screen cannot qualify TX power or Wi-Fi by EVM alone.')


def owner_current_gate(contract,architecture=None,*,design=None):
    """Current block/rail accounting, without inferred pin or transient limits."""
    from rf_quality_budget import current_allocation
    if architecture is None:
        design=b.design_for_contract(contract,design)
        architecture=design.architecture
    elif design is not None and (design.contract!=contract or design.architecture!=architecture):
        raise ValueError('Current allocation documents conflict with supplied design')
    cases=[]
    for mode in ('rf_rx','rf_tx','wired','usb'):
        branch=architecture['resource_policy']['primary_current_case_by_mode'].get(mode)
        allocation=current_allocation(architecture,mode,branch=branch)
        rails={rail:value/1000 for rail,value in allocation['by_rail_ma'].items()}
        if abs(sum(rails.values())-allocation['total_ma']/1000)>1e-12:
            raise ValueError('Block-to-rail current attribution lost current')
        cases.append(dict(mode=mode,allocation=allocation,rail_current_a=rails,
            total_chip_current_a=allocation['total_ma']/1000,
            fits_mode_current_ceiling=allocation['meets_allocation']))
    return dict(design_provenance=None if design is None else design.provenance(),
        model_role='independent_inventory_accounting' if design is None else 'shared_design_current_allocation',
        selected_planning_case=cases[0],cases=cases,
        status='within_mode_allocations' if all(x['fits_mode_current_ceiling'] for x in cases) else 'allocation_exceeded',
        physical_pin_current_qualification=False,
        scope='Current architecture block allocations summed by their assigned supply, including the separate CONV branch. Selected source override applied once; no overlap refund or converter-current reattribution. These are planning ceilings, not measured demand, individual bond limits or transient supply qualification.')


def tx_current_environment(contract,*,design=None,sensitivity_ps_per_mv=.025,supply_sign=-1.):
    """Design-bound network for explicitly imposed numerical current probes."""
    design=b.design_for_contract(contract,design)
    config=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64)
    scenario=Scenario()
    env=b.configured_environment(config,scenario)
    env['reference_load_parameters']=dict(differential=design.contract['physical_services']['external_clock_input']['input_model'])
    env['local_supply_sensitivity_ps_per_mv']=sensitivity_ps_per_mv
    env['local_supply_delay_sign']=supply_sign
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),result_role='numerical_component_diagnostic',
        probe_assumptions=dict(sensitivity_ps_per_mv=sensitivity_ps_per_mv,supply_sign=supply_sign,
            current='Explicit imposed waveform, not inferred chip switching demand',
            clock='Linear differential-input coupling; no delivered-clock admission'))
    return env,context


def tx_load_numerics(contract,*,design=None):
    """Separate current-grid truncation from periodic-guard error cheaply."""
    import numpy as np
    from converter_dynamics import sampled_load_response,feedback_change
    env,context=tx_current_environment(contract,design=design)
    origin=330e-6;source_step=.03125e-9
    relative=np.arange(32000)*source_step;times=origin+relative
    rows=[]
    def observed(response):
        mask=(response['times_s']>=origin)&(response['times_s']<=origin+1e-6)
        return {k:(v[mask] if isinstance(v,np.ndarray) and v.shape==mask.shape else v) for k,v in response.items()}
    for fall in (0.,20e-9):
        rise=np.clip((relative-100e-9)/50e-9,0.,1.)
        mute=(relative<600e-9).astype(float) if fall==0 else np.clip((600e-9-relative)/fall,0.,1.)
        current=-.007*(rise*mute)**2
        reference,reference_report=sampled_load_response(times,current,env,grid_s=source_step,guard_s=4e-6,method='coarse_fft')
        cases=[]
        for grid,guard in [(x*1e-9,4e-6) for x in (1.,.5,.25,.125,.0625)]+[(.125e-9,x*1e-6) for x in (1.,2.,8.)]:
            response,report=sampled_load_response(times,current,env,grid_s=grid,guard_s=guard,method='coarse_fft')
            comparison=dict(grid_s=grid,guard_s=guard,load=report,
                comparison_to_finest=feedback_change(observed(response),observed(reference)))
            if grid==.125e-9 and guard==4e-6:guard_reference=response
            if grid==.125e-9 and guard!=4e-6:
                comparison['guard_only_comparison']=feedback_change(observed(response),observed(guard_reference))
            cases.append(comparison)
        rows.append(dict(mute_fall_s=fall,reference_grid_s=source_step,reference_guard_s=4e-6,
            reference_load=reference_report,cases=cases))
    return dict(context,cases=rows,scope='Selected package and differential-input coupling. Fixed 1us, 7mA release waveform, 50ns voltage-envelope rise, hard or 20ns voltage-envelope fall, squared envelope current; same source samples across grids. Current solver retains assigned 200ps pole. Compare only active 1us interval. Grid and guard changes isolated. Finest FFT is a numerical comparator, not an exact transient; this isolates a mechanism and does not replace full-packet refinement or characterize silicon.')


def tx_current_tone_controls(contract,*,design=None):
    """Compare resampled current propagation to its known carrier phasor."""
    import numpy as np
    from converter_dynamics import sampled_load_response,coupled_reference_load_transfer
    env,context=tx_current_environment(contract,design=design)
    step=.03125e-9;times=np.arange(64000)*step;amplitude=.001;rows=[]
    for frequency in (37.5e6,100e6,312.5e6,625e6,900e6,1250e6):
        current=amplitude*np.cos(2*np.pi*frequency*(times+step/2))
        ports=coupled_reference_load_transfer(np.array([frequency]),env['network'],**env['reference_load_parameters'])
        # Fundamental of the source's piecewise-constant, midpoint-sampled
        # cosine. Source-hold images and finite turn-on/off transients remain
        # outside this analytic fundamental comparator.
        expected=amplitude*np.sinc(frequency*step)*ports['rail_v_per_a'][0]/(1+2j*np.pi*frequency*.2e-9)
        # Independent continuous-frequency image sum at native hold midpoints.
        # Separate asymptotic direct feedthrough so the remaining sum converges
        # quickly; sum_k sinc(f*dt+k)=1 reconstructs that term exactly.
        limit=coupled_reference_load_transfer(np.array([1e18]),env['network'],**env['reference_load_parameters'])['rail_v_per_a'][0]/(1+2j*np.pi*1e18*.2e-9)
        direct=float(limit.real);images=np.arange(-256,257);frequencies=frequency+images/step
        image_transfer=coupled_reference_load_transfer(abs(frequencies),env['network'],**env['reference_load_parameters'])['rail_v_per_a']/(1+2j*np.pi*abs(frequencies)*.2e-9)
        image_transfer=np.where(frequencies<0,image_transfer.conjugate(),image_transfer)
        expected_native=amplitude*(direct+sum(np.sinc(frequencies*step)*(image_transfer-direct)))

        for grid,method in [(x,'coarse_fft') for x in (1e-9,.5e-9,.125e-9,step)]+[(step,'native_modal')]:
            response,_=sampled_load_response(times,current,env,grid_s=grid,guard_s=2e-6,method=method)
            mask=(response['times_s']>=.5e-6)&(response['times_s']<1.5e-6)
            t=response['times_s'][mask];voltage=response['rail_v'][mask]
            basis=np.column_stack((np.cos(2*np.pi*frequency*t),np.sin(2*np.pi*frequency*t),np.ones(len(t))))
            coefficients=np.linalg.lstsq(basis,voltage,rcond=None)[0]
            measured=coefficients[0]-1j*coefficients[1]
            folded=abs((frequency+.5/grid)%(1/grid)-.5/grid)
            rows.append(dict(native_held_input_relative_error=None if method!='native_modal' else float(abs(measured-expected_native)/abs(expected_native)),
                method=method,frequency_hz=frequency,grid_s=grid,grid_nyquist_hz=.5/grid,
                folded_frequency_hz=folded,frequency_above_grid_nyquist=bool(frequency>.5/grid),
                expected_rail_peak_v=float(abs(expected)),measured_rail_peak_v=float(abs(measured)),
                complex_relative_error=float(abs(measured-expected)/abs(expected)),
                amplitude_ratio=float(abs(measured/expected)),phase_error_rad=float(np.angle(measured/expected)),
                fit_residual_rms_v=float(np.sqrt(np.mean((voltage-basis@coefficients)**2)))))
    return dict(context,cases=rows,source_grid_s=step,current_peak_a=amplitude,
        scope='Known sinusoidal current fundamental through the same continuous-frequency network and 200ps pole, compared with resampled FFT output at steady central samples. Tests representation, not the independently tested network itself. Source-hold images and finite switching transients are not part of the exact fundamental. A tone above grid Nyquist aliases; conserved integrated charge cannot preserve its frequency-dependent impedance or timing effect.')


def native_current_continuation(contract,*,design=None):
    import numpy as np
    from converter_dynamics import sampled_load_response
    env,context=tx_current_environment(contract,design=design,sensitivity_ps_per_mv=.1,supply_sign=1.)
    times=330e-6+np.arange(3200)*.125e-9
    current=np.zeros(len(times));current[100:1500]=-.007;current[1700:2500]=-.004
    whole,_=sampled_load_response(times,current,env,guard_s=20e-9)
    first,_=sampled_load_response(times[:1500],current[:1500],env,guard_s=2e-6)
    state=json.loads(json.dumps(first['final_state']))
    continued,report=sampled_load_response(times[1700:],current[1700:],env,initial_state=state,guard_s=20e-9)
    reset,_=sampled_load_response(times[1700:],current[1700:],env,guard_s=20e-9)
    fields=('rail_v','input_v','return_v','reference_fraction','delay_s')
    return dict(context,quiet_gap_s=report['quiet_gap_s'],committed_state_time_s=state['time_s'],
        continuation_peak_errors={k:float(np.max(abs(continued[k][:1500]-whole[k][1700:3200]))) for k in fields},
        reset_peak_errors={k:float(np.max(abs(reset[k][:1500]-whole[k][1700:3200]))) for k in fields},
        scope='Native incremental load-state serialization, quiet-gap decay and second activity window compared to one uninterrupted trace. First response extrapolates a 2us quiet tail but commits state only at the supplied input end. Zero incremental quiet current is an explicit warm-bias assumption. Not joined RX/TX or RF/wired protocol lifecycle qualification.')


def rx_memory_screen(contract,*,design=None):
    """Matched filter choices/history through the selected coupled packet RX."""
    import numpy as np
    from selected_rf import analog_modes,filter_settling_requirement,minimum_envelope_oversample
    carrier=2.426e9;sample_hz=carrier/64
    design=b.design_for_contract(contract,design);architecture=design.architecture
    raw,context=packet_environment(contract,architecture,gain_db=39.,wanted_dbm=-67.,blocker_dbm=-50.,design=design)
    raw['adc_switching']=dict(sample_hz=sample_hz,mean_a=b.adc_pair_current_allocation(raw),pulse_tau_s=.2e-9,harmonics=128)
    environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=-1.)
    context['probe_assumptions']=dict(adc_switching=raw['adc_switching'],supply_delay_sign=-1.,
        filter_history='Assigned filter-input history and candidate transfer functions')
    if environment is None:return dict(context,clock=clock,verdict='clock_rejected')
    steps=max(256,minimum_envelope_oversample(environment,sample_hz=sample_hz,guard_hz=3.1e6))
    cutoff=.5e6;amplitude=.05;maximum_gain_db=b.receiver_inventory_options(environment)['maximum_gain_db']
    rows=[]
    for family in ('rx_all_pole_control','rx_finite_zero'):
        requirement=filter_settling_requirement(family=family,cutoff_hz=cutoff,
            past_input_bound=amplitude,error_budget=1/1024/10**(maximum_gain_db/20))
        residues,poles=analog_modes(family)
        for history,age in (('zero_state',None),('prior_tone',0.),('qualified_prior_tone',requirement['settling_s'])):
            state=None
            if age is not None:
                # A continuous complex sinusoid at cutoff before record time -age,
                # then zero old forcing. No packet truth determines its phase.
                modes=amplitude/(1j-poles)*np.exp(poles*2*np.pi*cutoff*age)
                state=dict(family=family,cutoff_hz=cutoff,modes=np.column_stack((modes.real,modes.imag)).tolist())
            options=dict(lo_divider=64,blocker_offsets_hz=(2e6,),noise_figure_db=architecture['blocks']['lna']['parameters']['noise_figure_db'],rx_cutoff_hz=cutoff,
                rx_filter_family=family,filter_initial_state=state,
                input_iip3_dbm=architecture['blocks']['lna']['parameters']['iip3_dbm'],converter_bits=architecture['blocks']['adc_i']['parameters']['native_bits'],aperture_rms_s=environment['adc_noise_parameters']['aperture_rms_s'],dynamic_rail=True,
                sar_parameters=b.environment_converter_parameters(environment),mixer_substeps=steps)
            received,_=b.coupled_scan_request(environment,contract,rx_options=options,
                stimulus=dict(seed=81,wanted_dbm=-67.,blocker_dbm=-50.,blocker_modulation='gfsk_prbs15'),
                progress=lambda step:print('RX memory',family,history,'iteration',step['iteration'],flush=True))
            valid=min(received['converter']['evaluated_supply_interval_v'])>=2.5
            converged=received['reference_feedback']['numerical_feedback_converged']
            verdict=('supply_outside_model_domain' if not valid else 'feedback_unresolved' if not converged else
                'conditional_single_packet_decode' if received['correct_request'] else 'packet_failed')
            rows.append(dict(family=family,history=history,quiet_age_s=age,settling_requirement=requirement,
                verdict=verdict,receiver=received))
            print('RX memory',family,history,verdict,flush=True)
    return dict(context,clock=clock,cases=rows,prehistory_filter_input_peak_v=amplitude,
        prehistory_frequency_hz=cutoff,maximum_downstream_gain_db=maximum_gain_db,
        scope='Matched selected 0.25 nH return/0.2 nH die ESL, internal/ADC activity, differential clock, moving rails, native SAR and reference-recharge feedback. Same real BLE request, +2 MHz modulated blocker, seed and NF/IIP3 assumptions as the joint screen. Prior 50 mV complex sinusoid is specified at the filter input after early gain/mixing, with phase zero at removal; it is not an independently simulated earlier RF/LO/AGC/package trajectory. Old filter state survives record start; zero-state control is explicit. Quiet-age mitigation bounds old-history error to nominal 1/1024 ADC volt at the shared design maximum PGA gain; reference variation and new-input noise/blocking remain in the packet model. No phase/statistical sweep, saturation/internal-node proof, preceding TX leakage/bias wake, absolute previous-record timing or protocol verdict.')


def filter_realization_screen(contract,*,design=None):
    """Finite-integrator requirement boundary, then the same coupled RX chain."""
    import numpy as np
    from selected_rf import analog_modes
    cutoff=9.53125e6
    frequency=np.linspace(0,1,2001)
    transfer=[]
    configurations=[('ideal',None,None),('uncompensated_16',16.,None),
        ('uncompensated_32',32.,None),('uncompensated_128',128.,None),
        ('retuned_32',32.,32.),('retuned_slow',28.8,32.),('retuned_fast',35.2,32.)]
    _,ideal_poles=analog_modes('rx_finite_zero')
    stability_ratio=float(max(ideal_poles.imag**2/(-ideal_poles.real)))
    for name,ratio,retune in configurations:
        residues,poles=analog_modes('rx_finite_zero',integrator_ratio=ratio,retune_ratio=retune)
        stable=bool(np.all(poles.real<0))
        row=dict(name=name,integrator_ratio=ratio,retune_ratio=retune,stable=stable,
            rightmost_normalized_pole_real=float(max(poles.real)))
        if stable:
            h=np.sum(residues/(1j*frequency[:,None]-poles),axis=1)
            band=20*np.log10(abs(h))
            blocker=np.sum(residues/(1j*12e6/cutoff-poles))
            row.update(sampled_passband_gain_db=[float(min(band)),float(max(band))],
                blocker_gain_db=float(20*np.log10(abs(blocker))))
        transfer.append(row)
    design=b.design_for_contract(contract,design);architecture=design.architecture
    raw,context=packet_environment(contract,architecture,
        gain_db=max(architecture['blocks']['pga_i']['parameters']['gain_db']),
        wanted_dbm=-65.,blocker_dbm=-30.,reference_hz=2.4e9,design=design)
    context['probe_assumptions']=dict(supply_delay_sign=-1.,
        filter_realization='Explicit finite-integrator and retuning hypotheses, not legal circuit settings')
    raw['adc_switching']=dict(sample_hz=2.4e9/64,mean_a=b.adc_pair_current_allocation(raw),pulse_tau_s=.2e-9,harmonics=128)
    context['probe_assumptions']['adc_switching']=raw['adc_switching']
    environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=-1.)
    rows=[]
    if environment is not None:
        for name,ratio,retune in configurations:
            if name in ('uncompensated_16','uncompensated_128'):continue
            result=b.coupled_wideband_feedback(environment,filter_integrator_ratio=ratio,filter_retune_ratio=retune)
            converter=result['receiver']['gain_cases'][0]['adc']
            valid=converter['evaluated_supply_interval_v'][0]>=2.5 and converter['evaluated_supply_interval_v'][1]<=3.6
            rows.append(dict(name=name,filter_integrator_ratio=ratio,filter_retune_ratio=retune,
                evaluated_supply_valid=valid,result=result))
            print('Filter realization',name,'converged',result['numerical_feedback_converged'],
                'observation',result['receiver']['gain_cases'][0]['observation'],flush=True)
    costs=[];support_budget=sum(architecture['blocks'][name]['resource_allocation']['current_budget_ma']['rf_rx']
                               for name in ('rxfilter_i','rxfilter_q'))/1000
    for ratio in (32.,128.):
        for cap in (.1e-12,.5e-12,1e-12):
            for efficiency in (5.,10.,15.):
                current=10*2*np.pi*ratio*cutoff*cap/efficiency
                costs.append(dict(integrator_ratio=ratio,effective_pole_hz=ratio*cutoff,
                    effective_cap_per_stage_f=cap,gm_over_id_per_v=efficiency,stages=10,
                    illustrative_bias_a=current,remaining_of_paired_rx_filter_budget_a=support_budget-current))
    return dict(context,transfer_cases=transfer,uncompensated_stability_ratio_lower_limit=stability_ratio,
        cutoff_hz=cutoff,clock=clock,coupled_receiver_cases=rows,bias_scenarios=costs,paired_rx_filter_budget_a=support_budget,
        definition='Replace each normalized ideal integrator 1/z by 1/[z*(1+z/rho)], hence H(z) becomes H(z+z*z/rho). Retuning maps intended prototype zeros and poles to p+p*p/rho_nominal before the actual substitution; weights are unconstrained. Stability threshold is max(Im(p)^2/-Re(p)); equality has a marginal imaginary-axis pole.',
        scope='Explicit linear realization surrogate, not a transistor topology or universal op-amp GBW law. Same selected package/timing/internal/ADC activity and causal SAR/recharge wideband diagnostic. Wanted -65 dBm, blocker -30 dBm at +12 MHz, fixed 42 dB PGA, assigned NF/IIP3 and ideal DATA framing/training; not a standards-valid packet or PER. Retune requires realizable coefficients and characterization; +/-10% actual pole drift keeps nominal coefficients. No extra amplifier noise, slew/internal saturation, finite DC gain, mismatch or additional poles. Bias scenarios assume ten independent gm/C stages and gm/Id; exclude compensation, mirrors, output stages, references and other RF support. They are conditional cost requirements, not GF180 predictions or proof of fit within the paired RX-filter allocation.')


def reciprocal_allocation_lower_bound(matrix,weights,point):
    """Convex dual bound for min a*x, M*(1/x)<=1, x>=1.

    Any nonnegative multipliers give a lower bound. NNLS estimates useful ones
    from active constraints; the final separable minimization, not optimizer
    success, supplies the bound. Arithmetic is floating-point, not interval.
    """
    import numpy as np
    from scipy import optimize
    M=np.asarray(matrix,float);a=np.asarray(weights,float);x=np.asarray(point,float)
    if (M.ndim!=2 or M.shape[1]!=len(a) or x.shape!=a.shape or
            not np.all(np.isfinite(M)) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(x)) or
            np.any(M<0) or np.any(a<=0) or np.any(x<1-1e-8)):
        raise ValueError('Positive finite allocation data required')
    active=np.flatnonzero(M@(1/x)>=1-1e-6);bounds=np.flatnonzero(x<=1+1e-6)
    J=np.c_[(M[active]/x[None,:]**2).T,np.eye(len(x))[:,bounds]]
    multipliers=np.zeros(len(M))
    if J.shape[1]:
        norm=np.linalg.norm(J,axis=0)
        fitted,_=optimize.nnls(J/norm,a,maxiter=10000)
        multipliers[active]=(fitted/norm)[:len(active)]
    v=M.T@multipliers
    minimizer=np.maximum(1.,np.sqrt(v/a))
    lower=float(a@minimizer+sum(v/minimizer)-sum(multipliers))
    return dict(lower_bound=max(0.,lower),evaluated_objective=float(a@x),
        gap=float(a@x-max(0.,lower)),multipliers_nonnegative=bool(np.all(multipliers>=0)))


def domain_rlc_impedance(frequency_hz,capacitance_f,branch_r_ohm,*,branch_l_h=2e-9,
                         return_l_h=.25e-9,die_esl_h=.2e-9,die_esr_ohm=.5,include_external_return=False,local_cap_esl_h=None):
    """Rail-to-common-die-return impedance; no independent quiet grounds.

    Board shunt precedes domain feeds. Each local capacitor returns to common
    die ground. ESR/ESL scale inversely with capacitor fraction, preserving the
    aggregate when tied. This is an assigned topology, not a package extraction.
    """
    import numpy as np
    c=np.asarray(capacitance_f,float);w=2*np.pi*frequency_hz
    if frequency_hz<0 or np.any(c<=0) or branch_r_ohm<=0:
        raise ValueError('Nonnegative frequency and positive C/R required')
    source=.1+1j*w*2e-9
    if w:
        board=.02+1j*w*1e-9+1/(1j*w*1e-6)
        source=1/(1/source+1/board)
    common=source+.02+1j*w*return_l_h
    feed=np.diag(np.full(len(c),branch_r_ohm+1j*w*branch_l_h))+common*np.ones((len(c),len(c)))
    admittance=np.linalg.inv(feed)
    if w:
        fraction=c/sum(c)
        local_l=die_esl_h/fraction if local_cap_esl_h is None else np.asarray(local_cap_esl_h,float)
        if local_l.shape!=c.shape or np.any(~np.isfinite(local_l)) or np.any(local_l<0):
            raise ValueError("One finite nonnegative local loop inductance per capacitor required")
        cap_z=die_esr_ohm/fraction+1j*w*local_l+1/(1j*w*c)
        admittance+=np.diag(1/cap_z)
    impedance=np.linalg.inv(admittance)
    if include_external_return:
        return impedance,-impedance@np.linalg.solve(feed,np.ones(len(c)))*(.02+1j*w*return_l_h)
    return impedance


def recorded_library_inputs(**records):
    """Identify pinned characterization inputs without claiming silicon validation."""
    return {name:dict(record_sha256=hashlib.sha256(
                json.dumps(record,sort_keys=True,allow_nan=False).encode()).hexdigest(),
            source_records=deepcopy(record['sources'] if 'sources' in record else [record['source']]))
            for name,record in records.items()}


def host_input_library_evidence():
    """Pinned public characterization energy; not a transient current fit."""
    import urllib.request,re
    import numpy as np
    commit='2aeec51ea2824b6cc0b396acfc39f4535f40b23a'
    root='https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io/'+commit+'/'
    files=['cells/in_c/gf180mcu_fd_io__in_c__tt_025C_3v30.lib','liberty/gf180mcu_fd_io__tt_025C_3v30.lib']
    contents={name:urllib.request.urlopen(root+name,timeout=30).read() for name in files}
    cell=contents[files[0]].decode();header=contents[files[1]].decode()
    assert 'voltage_unit : "1V"' in header and '"pf"' in header and 'nom_voltage : 3.300000' in header
    output=cell[cell.index('pin ("Y")'):];tables=[]
    for name in ('rise_power','fall_power'):
        part=output[output.index(name):];start=part.index('values(')
        text=part[start+7:part.index(');',start)]
        tables.append(np.array([float(x) for x in re.findall(r'-?\d+\.\d+',text)]).reshape(3,6))
    net=tables[0]+tables[1];load=np.array([0,.04,.1,.3,.4,.5])
    including_load=net+3.3**2*load
    return dict(cell='gf180mcu_fd_io__in_c',corner='TT 3.3 V 25 C',
        sources=[dict(url=root+n,sha256=hashlib.sha256(contents[n]).hexdigest()) for n in files],
        input_slew_ns=[.08,.5,1.],output_load_pf=load.tolist(),
        rise_internal_energy_pj=tables[0].tolist(),fall_internal_energy_pj=tables[1].tolist(),
        net_cycle_internal_energy_pj=net.tolist(),
        equivalent_average_internal_charge_per_transition_pc=[float(net.min()/6.6),float(net.max()/6.6)],
        equivalent_charge_including_output_load_pc=[float(including_load.min()/6.6),float(including_load.max()/6.6)],
        pad_capacitance_pf=3.135837,
        energy_unit_basis='Internal-power table energy scale V_unit^2*C_unit = pJ. Do not use leakage_power_unit or current_unit as the dynamic-energy scale. Signed rise and fall entries are summed for a full cycle; never clamp negative entries or interpret them as negative passive current pulses.',
        unit_reader_reference='https://github.com/parallaxsw/OpenSTA/blob/master/liberty/LibertyReader.cc (energyScale and readInternalPowerGroups)',
        scope='Public PDK library characterization, not measured silicon or the custom host receiver. Equivalent charge is average over two transitions. Output-load switching term is separate and may already belong to another modeled power domain. No peak current, edge shape, supply-port split, bandwidth, mismatch or temperature-range bound follows. Preserve 7 pC as an adverse unvalidated scenario, not a measured receiver value.')



def host_output_library_evidence():
    """Pinned output PAD energy, preserving drive/slew conditions separately."""
    import urllib.request,re
    import numpy as np
    commit='2aeec51ea2824b6cc0b396acfc39f4535f40b23a'
    root='https://raw.githubusercontent.com/google/globalfoundries-pdk-libs-gf180mcu_fd_io/'+commit+'/'
    name='cells/bi_t/gf180mcu_fd_io__bi_t__tt_025C_3v30.lib'
    raw=urllib.request.urlopen(root+name,timeout=30).read()
    pad=raw.decode().split('pin ("PAD") {',1)[1].split('\n\t\tpin (',1)[0]
    rows=[]
    for group in pad.split('internal_power () {')[1:]:
        if not group.lstrip().startswith('related_pin : "A";'):continue
        condition_match=re.search(r'when : "([^"]+)"',group.split('rise_power',1)[0])
        if condition_match is None:continue  # unconditional fallback is not a ninth drive setting
        condition=condition_match.group(1)
        tables=[]
        for kind in ('rise_power','fall_power'):
            table=group.split(kind,1)[1].split('}',1)[0]
            axes=[np.fromstring(re.search('index_'+str(i)+r'\("([^"]+)"\)',table).group(1),sep=',') for i in (1,2)]
            data=table.split('values(',1)[1].split(');',1)[0]
            values=np.array([float(v) for v in re.findall(r'-?\d+\.\d+',data)]).reshape(len(axes[0]),len(axes[1]))
            tables.append(values)
        energy=tables[0]+tables[1]
        at10=np.array([np.interp(10.,axes[1],row) for row in energy])
        rows.append(dict(condition=condition,input_slew_ns=axes[0].tolist(),load_pf=axes[1].tolist(),
            cycle_internal_energy_pj=energy.tolist(),
            equivalent_internal_charge_at_10pf_pc=(at10/(2*3.3)).tolist()))
    assert len(rows)==8
    timing_groups={}
    for group in pad.split('timing () {')[1:]:
        header=group.split('cell_rise',1)[0]
        match=re.search(r'when : "([^"]+)"',header)
        if 'related_pin : "A";' not in header or match is None:continue
        timing_groups[match.group(1)]=group
    for row in rows:
        group=timing_groups[row['condition']];observations={}
        for kind in ('cell_rise','cell_fall','rise_transition','fall_transition'):
            table=group.split(kind,1)[1].split('}',1)[0]
            axes=[np.fromstring(re.search('index_'+str(i)+r'\("([^"]+)"\)',table).group(1),sep=',') for i in (1,2)]
            data=table.split('values(',1)[1].split(');',1)[0]
            values=np.array([float(v) for v in re.findall(r'-?\d+\.\d+',data)]).reshape(len(axes[0]),len(axes[1]))
            assert np.allclose(axes[0],row['input_slew_ns'])
            observations[kind]={str(load):[float(np.interp(load,axes[1],v)) for v in values]
                for load in (6.,8.977816,10.,12.977816)}
        row['timing_ns_by_table_load_pf']=observations
    charges=[q for r in rows for q in r['equivalent_internal_charge_at_10pf_pc']]
    return dict(cell='gf180mcu_fd_io__bi_t',corner='TT 3.3 V 25 C',
        source=dict(url=root+name,sha256=hashlib.sha256(raw).hexdigest()),cases=rows,
        internal_charge_at_10pf_range_pc=[min(charges),max(charges)],
        assumed_d2h_internal_charge_pc=7.,
        timing_load_scope='Timing axis begins at 2.977816 pF, equal to listed PAD capacitance; power axis begins at zero. Preserve both 10 pF and 10+2.977816 pF timing queries pending characterization load-convention validation. Delays are not maximum data-rate limits; transitions are not current-pulse widths.',
        scope='Public characterization, not measured silicon or selected custom output circuitry. PAD related-A arcs only; fixed OE/IE/drive/slew controls. Sum signed rise/fall energy per cycle; divide by 2V for equivalent average transition charge. Linear interpolation to 10 pF. External CV-squared charging remains separate. Input-pin energy, supply-port split, pulse shape, output timing, PVT and custom-cell performance are not qualified. Energy-unit basis follows the existing pinned input-library evidence.')



def output_host_current_budget(contract,output_evidence,input_evidence,*,d2h_rates=None):
    """Matched per-bank mean-current requirements; not peak-current signoff."""
    qin=max(input_evidence['equivalent_charge_including_output_load_pc'])*1e-12
    ceiling=next(x for x in contract['power']['domains'] if x['id']=='HOST')['per_connection_budget_ma']*1e-3
    allowance=contract['power']['screen_other_current_allowance_ma_per_segment']*1e-3
    host=contract['physical_services']['host_output']
    voltage=host['voltage_v']
    if voltage!=3.3:
        raise ValueError('Pinned host library energy is characterized at 3.3 V only')
    profile=contract['transport']['profiles']['ddr156']
    input_rate=profile['clock_hz']*profile['edges']
    rates=(150e6,host['maximum_word_rate_hz']) if d2h_rates is None else tuple(d2h_rates)
    import math
    if not rates or any(not math.isfinite(r) or r<=0 or r>host['maximum_word_rate_hz'] for r in rates):
        raise ValueError('Host comparison rates must fit the declared transport range')
    rows=[]
    for load_pf in dict.fromkeys(host[k]*1e12 for k in
            ('full_rate_external_load_target_f','heavy_load_comparison_f')):
        for setting in output_evidence['cases']:
            if not min(setting['load_pf'])<=load_pf<=max(setting['load_pf']):
                raise ValueError('Host load outside characterized interpolation range')
            import numpy as np
            qout=max(np.interp(load_pf,setting['load_pf'],row) for row in setting['cycle_internal_energy_pj'])/(2*3.3)*1e-12
            for rate in rates:
                for activity,rise,toggle in [('random_mean',.25,.5),('alternating',.5,1.)]:
                    banks=[]
                    for segment in contract['power']['host_segments']:
                        clock=int('D2H_CLK' in segment['fast_outputs'])
                        data=len(segment['fast_outputs'])-clock
                        charge_current=load_pf*1e-12*3.3*rate*(data*rise+clock*.5)
                        internal_current=qout*rate*(data*toggle+clock)
                        input_current=qin*input_rate*len(segment['inputs'])
                        total=charge_current+internal_current+input_current+allowance
                        banks.append(dict(bank=segment['id'],external_charging_a=charge_current,
                            output_internal_a=internal_current,input_internal_a=input_current,
                            other_allowance_a=allowance,total_a=total,margin_a=ceiling-total))
                    rows.append(dict(condition=setting['condition'],output_load_pf=load_pf,d2h_word_hz=rate,activity=activity,
                        output_equivalent_charge_pc=qout*1e12,banks=banks,
                        fits_both_bank_mean_ceilings=all(x['margin_a']>=0 for x in banks)))
    return dict(cases=rows,h2d_word_hz=input_rate,output_voltage_v=voltage,scope='Shared selected/heavy output loads at 3.3 V, conditional nominal PAD energy at maximum listed input-slew charge; H2D held alternating at shared ddr156 rate using input-library including-Y-load upper scenario. External output charging counted once. Includes existing per-bank 2 mA other allowance, not additional current on top of HOST reservation. No 1.25 screen multiplier applied: raw current versus planning ceiling only. Control activity, power-port split, peak/EM, timing, package and PVT are unqualified. Random mean does not constrain legal alternating data.')


def finite_host_edge_network_screen(*,receiver_charge_c=7e-12,output_cap_f=10e-12,output_internal_charge_c=7e-12,local_cap_esl_h=None,edges=(0.,100e-12),scales=(1,4,16,64,256)):
    """Fixed-network source convergence, not capacitor selection or rail closure."""
    import numpy as np
    from robustness_envelope import host_harmonic_current,h2d_current_ports
    names=['core','host_a','host_b','wire_a','wire_b','rf','timing']
    cap=np.array([180,30,30,10,10,180,60])*2e-12
    distribution=np.array([0,.5,.5,0,0,0,0]);cache={};rows=[]
    grid=131072;period=160e-9;previous={}
    def transfer(f):
        if f not in cache:cache[f]=domain_rlc_impedance(f,cap,1.,include_external_return=True,local_cap_esl_h=local_cap_esl_h)
        return cache[f]
    for edge in edges:
        for scale in scales:
            components={key:np.zeros((grid//2+1,7),complex) for key in
                ('d2h_load_charging','d2h_internal_switching','h2d_internal_load','h2d_external_return')}
            for n in range(1,12*scale+1):
                f=n*75e6;z,_=transfer(f)
                charging=host_harmonic_current(f,150e6,n,current_edge_s=edge,internal_charge_c=0.,output_cap_f=output_cap_f)
                combined=host_harmonic_current(f,150e6,n,current_edge_s=edge,internal_charge_c=output_internal_charge_c,output_cap_f=output_cap_f)
                components['d2h_load_charging'][12*n]+=-z@distribution*charging
                components['d2h_internal_switching'][12*n]+=-z@distribution*(combined-charging)
            for n in range(1,6*scale+1):
                f=n*156.25e6;z,ret=transfer(f)
                ports=h2d_current_ports(f,312.5e6,n,internal_charge_c=receiver_charge_c,alternating=True,current_edge_s=edge)
                components['h2d_internal_load'][25*n]+=-z@distribution*ports['chip_internal_peak_a']
                components['h2d_external_return'][25*n]+=ret*ports['external_cap_return_peak_a']
            spectrum=sum(components.values())
            wave=np.fft.irfft(spectrum*(grid/2),n=grid,axis=0)
            source_waves={key:np.fft.irfft(value*(grid/2),n=grid,axis=0) for key,value in components.items()}
            residual=float(np.max(abs(wave-sum(source_waves.values()))))
            assert residual<1e-12
            prior=previous.get(edge)
            rows.append(dict(current_edge_s=edge,harmonics=[12*scale,6*scale],
                sampled_min_v=wave.min(axis=0).tolist(),sampled_max_v=wave.max(axis=0).tolist(),
                maximum_waveform_change_v=None if prior is None else float(np.max(abs(wave-prior))),
                maximum_rail_ripple_v=float(np.max(abs(wave))),
                source_peak_absolute_v={key:np.max(abs(value),axis=0).tolist() for key,value in source_waves.items()},
                source_superposition_residual_v=residual))
            previous[edge]=wave
    return dict(local_cap_esl_h=(.2e-9/(cap/sum(cap))).tolist() if local_cap_esl_h is None else list(local_cap_esl_h),output_cap_f=output_cap_f,output_internal_charge_c=output_internal_charge_c,receiver_charge_c=receiver_charge_c,receiver_mean_current_a=11*receiver_charge_c*312.5e6,domains=names,cases=rows,total_local_cap_f=float(sum(cap)),
        branch_r_ohm=1.,branch_l_h=2e-9,return_l_h=.25e-9,die_esl_h=.2e-9,die_esr_ohm=.5,
        sample_step_s=period/grid,
        scope='Fixed former 1 nF comparison network, not a selected reservoir. Host-only AC forcing: D2H mean-data and alternating H2D, split bank supply and separate external return; charge/DC unchanged. 100 ps kernel half-width is an assigned source hypothesis with 200 ps support, not a measured GPIO edge. No ADC/core/timing/reference switching, input clock, arbitrary phase, device feedback, DC rail-domain validity or rigorous infinite-tail bound. High-frequency lumped extrapolation diagnoses numerical convergence, not physical accuracy.')


def filter_budget_screen(contract,*,design=None):
    """Voltage-scaled state/noise allocation; no modal-state headroom fiction."""
    import itertools
    import numpy as np
    from scipy import linalg,optimize
    from selected_rf import rx_filter_state_space
    design=b.design_for_contract(contract,design);architecture=design.architecture
    conditions=Scenario().operating_conditions(design)
    filters=[architecture['blocks'][name]['parameters'] for name in ('rxfilter_i','rxfilter_q')]
    if any(f['order']!=5 for f in filters):
        raise ValueError('Filter budget adapter requires fifth-order paired filters')
    cutoff=min(f['cutoff_hz'][1] for f in filters)
    if cutoff<max(f['cutoff_hz'][0] for f in filters):
        raise ValueError('Paired filter cutoff ranges do not overlap')
    rate=2*np.pi*cutoff;kT=1.380649e-23*conditions['temperature_k']
    support=sum(architecture['blocks'][name]['resource_allocation']['current_budget_ma']['rf_rx']
                for name in ('rxfilter_i','rxfilter_q'))/1000
    rows=[]
    for order in itertools.permutations(range(3)):
        for pairing in ((0,1),(1,0)):
            m=rx_filter_state_space(order=order,zero_pairing=pairing,integrator_ratio=32.,retune_ratio=32.)
            A,B,C,N=m['A'],m['B'],m['C'],m['noise_inputs']
            assert max(np.linalg.eigvals(A).real)<0 and m['D']==0
            def bandwidth(v):
                P=linalg.solve_continuous_lyapunov(A,-np.outer(v,v))
                return float(rate/2*(C@P@C))
            signal_bw=bandwidth(B);noise_bw=np.array([bandwidth(v) for v in N.T])
            nf_grid=np.linspace(0,1,401)
            forcing=np.c_[B,N]
            state=np.linalg.solve(1j*nf_grid[:,None,None]*np.eye(len(B))-A,
                np.broadcast_to(forcing,(len(nf_grid),)+forcing.shape))
            transfer=np.einsum('i,fij->fj',C,state)
            signal_power=abs(transfer[:,0])**2;noise_power=abs(transfer[:,1:])**2
            def nodes(frequency):
                x=np.linalg.solve(1j*(frequency/cutoff)[:,None,None]*np.eye(len(B))-A,
                    np.broadcast_to(B,(len(frequency),len(B)))[...,None])[...,0]
                return x@m['observers'].T+m['observer_direct']
            wanted_grid=np.linspace(0,10e6,401);wanted_nodes=abs(nodes(wanted_grid))
            wanted_peak=np.max(wanted_nodes,axis=0)
            blocker_peak=abs(nodes(np.array([12e6]))[0])
            wanted_slew=np.max(wanted_nodes[:,:5]*(2*np.pi*wanted_grid[:,None]),axis=0)
            blocker_slew=blocker_peak[:5]*(2*np.pi*12e6)
            # Steady tones at worst independently phased wanted/blocker origins;
            # sampled wanted frequency, not an OFDM crest-factor guarantee.
            swings=[]
            for wanted_dbm,blocker_dbm in ((-65.,-30.),(-40.,-30.),(-65.,-20.)):
                # A filter can retain excitation acquired at a higher rail;
                # do not cancel low headroom with simultaneous low input gain.
                scale=10*3.6/3.3
                source=lambda dbm:np.sqrt(100*1e-3*10**((dbm-2)/10))*scale
                peak=source(wanted_dbm)*wanted_peak+source(blocker_dbm)*blocker_peak
                slew=source(wanted_dbm)*wanted_slew+source(blocker_dbm)*blocker_slew
                swings.append(dict(wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,
                    maximum_input_gain_rail_v=3.6,minimum_headroom_rail_v=2.5,
                    sampled_node_peak_v=peak.tolist(),worst_node=m['observer_names'][int(np.argmax(peak))],
                    integration_node_slew_v_per_s=slew.tolist(),
                    resistor_absolute_current_per_cap_a_per_f=(rate*m['normalized_resistor_load_matrix']@np.r_[peak[:8],source(wanted_dbm)+source(blocker_dbm)]).tolist(),
                    maximum_peak_v=float(max(peak)),assigned_node_headroom_v=.8*2.5/3.3,
                    exceeds_assigned_headroom=bool(max(peak)>.8*2.5/3.3)))
            costs=[]
            for front_nf,gamma,efficiency,cap in ((3.,1.,10.,.5e-12),(5.,2.,5.,1e-12)):
                gain=10*2.5/3.3
                budget=100*kT*(10**.6-10**(front_nf/10))*gain**2*signal_bw
                weights=4*kT*gamma*noise_bw
                minimum=2*np.pi*32*cutoff*cap
                if np.sum(weights/minimum)<=budget:gm=np.full(len(weights),minimum)
                else:
                    lo=0.;hi=(sum(np.sqrt(weights))/budget)**2
                    for _ in range(80):
                        mid=(lo+hi)/2
                        candidate=np.maximum(minimum,np.sqrt(mid*weights))
                        if sum(weights/candidate)>budget:lo=mid
                        else:hi=mid
                    gm=np.maximum(minimum,np.sqrt(hi*weights))
                integrated_gm=gm.copy()
                def nf(g):
                    F=10**(front_nf/10)+(noise_power@(4*kT*gamma/g))/(100*kT*gain**2*signal_power)
                    return 10*np.log10(F)
                integrated_nf=nf(integrated_gm)
                # Convex constraints in positive gm: each frequency and the
                # integrated budget must fit, with a common bandwidth floor.
                M=4*kT*gamma*noise_power/(100*kT*gain**2*(10**.6-10**(front_nf/10))*signal_power[:,None]*minimum)
                M=np.vstack([M,weights/(budget*minimum)])
                initial=np.full(len(weights),max(1.,float(max(M.sum(axis=1))))*1.01)
                fit=optimize.minimize(lambda x:float(sum(x)),initial,jac=lambda x:np.ones_like(x),
                    bounds=[(1.,None)]*len(weights),method='SLSQP',
                    constraints=[dict(type='ineq',fun=lambda x:1-M@(1/x),jac=lambda x:M/x[None,:]**2)],
                    options=dict(ftol=1e-10,maxiter=300))
                if not fit.success or max(M@(1/fit.x))>1+1e-8:
                    raise ValueError('Noise/bandwidth allocation did not converge: '+fit.message)
                gm=minimum*fit.x;qualified_nf=nf(gm)
                current=2*sum(gm)/efficiency
                entry=dict(frontend_nf_db=front_nf,target_total_nf_db=6.,channel_noise_gamma=gamma,
                    gm_over_id_per_v=efficiency,minimum_effective_cap_per_integrator_f=cap,
                    required_effective_cap_per_integrator_f=(gm/(2*np.pi*32*cutoff)).tolist(),
                    effective_early_voltage_gain=gain,per_integrator_gm_s=gm.tolist(),
                    per_integrator_noise_v_rt_hz=np.sqrt(4*kT*gamma/gm).tolist(),
                    paired_iq_bias_a=float(current),remaining_rf_support_a=float(support-current),
                    filter_alone_exceeds_support=bool(current>support),
                    integrated_only_bias_a=float(2*sum(integrated_gm)/efficiency),
                    integrated_only_passband_nf_db=[float(min(integrated_nf)),float(max(integrated_nf))],
                    sampled_passband_nf_db=[float(min(qualified_nf)),float(max(qualified_nf))],
                    achieved_output_noise_variance_v2=float(sum(weights/gm)),
                    allowed_filter_output_noise_variance_v2=float(budget))
                # RC drive-noise PSD: 4kT*R0*sum(abs(local coefficients)),
                # R0=1/(w*Cint). Cint is distinct from amplifier pole capacitance.
                unit_c=1e-12;rates=rate*m['normalized_integrator_rates']
                resistor_weight=m['resistor_conductance_weights']
                MR=M*(minimum*resistor_weight/(gamma*rates*unit_c))[None,:]
                slew=np.asarray(swings[0]['integration_node_slew_v_per_s'])
                objective_weights=2*np.r_[np.full(5,minimum/efficiency),slew*unit_c]/.001
                seed=np.full(10,max(1.,float(max(M.sum(axis=1)+MR.sum(axis=1))))*1.01)
                passive=optimize.minimize(lambda x:float(objective_weights@x),seed,jac=lambda x:objective_weights,
                    bounds=[(1.,None)]*10,method='SLSQP',
                    constraints=[dict(type='ineq',fun=lambda x:1-M@(1/x[:5])-MR@(1/x[5:]),
                        jac=lambda x:np.c_[M/x[None,:5]**2,MR/x[None,5:]**2])],
                    options=dict(ftol=1e-10,maxiter=500))
                if not passive.success or max(M@(1/passive.x[:5])+MR@(1/passive.x[5:]))>1+1e-8:
                    raise ValueError('RC noise/drive allocation did not converge: '+passive.message)
                pgm=minimum*passive.x[:5];integration_c=unit_c*passive.x[5:]
                dual=reciprocal_allocation_lower_bound(np.c_[M,MR],objective_weights,passive.x)
                resistances=1/(rates*integration_c)
                density=4*kT*(gamma/pgm+resistor_weight*resistances)
                pnf=10*np.log10(10**(front_nf/10)+(noise_power@density)/(100*kT*gain**2*signal_power))
                input_bias=2*sum(pgm)/efficiency;drive_bias=2*sum(slew*integration_c)
                entry['rc_noise_and_capacitive_drive']=dict(
                    per_integrator_gm_s=pgm.tolist(),integration_cap_per_iq_f=integration_c.tolist(),
                    unit_input_resistance_ohm=resistances.tolist(),resistor_conductance_weights=resistor_weight.tolist(),
                    effective_amplifier_pole_cap_f=(pgm/(2*np.pi*32*cutoff)).tolist(),
                    paired_iq_input_bias_a=float(input_bias),paired_iq_separate_class_a_drive_a=float(drive_bias),
                    paired_iq_combined_current_a=float(input_bias+drive_bias),
                    convex_dual_current_lower_bound_a=dual['lower_bound']*.001,
                    optimization_gap_a=dual['gap']*.001,
                    remaining_rf_support_a=float(support-input_bias-drive_bias),
                    filter_alone_exceeds_support=bool(dual['lower_bound']*.001>support),
                    sampled_passband_nf_db=[float(min(pnf)),float(max(pnf))],
                    output_noise_variance_v2=float(noise_bw@density),
                    total_paired_integration_cap_f=float(2*sum(integration_c)),
                    plate_area_scenarios=[dict(density_ff_per_um2=d,
                        ideal_plate_area_mm2=float(2*sum(integration_c)/(d*1e-9)),
                        remaining_rf_area_mm2=float(contract['area_um2']['rf']/1e6-2*sum(integration_c)/(d*1e-9)))
                        for d in (.9,1.8)],
                    paired_capacitive_drive_by_tone_a=[float(2*np.dot(x['integration_node_slew_v_per_s'],integration_c)) for x in swings],
                    scope='Joint optimization for the first (-65/-30 dBm) tone stimulus only, subject to the same passband/integrated noise targets. Explicit active summing resistors add thermal noise; integrator-input amplifier noise retains the existing illustrative gamma/gm law. Separate input and class-A output banks reserve peak capacitive current, not a universal minimum or class-AB average. A convex dual bound checks numerical cost rejection within that model. Integration plate areas use existing 0.9/1.8 fF/um2 density scenarios, without routing/guard/tuning overhead or guaranteed provider availability; all other RF area must remain inside the 2.4 mm2 owner. Actual resistor-driver implementation, amplifier voltage-noise gain, compensation/loop stability with Cint, summer noise/current and physical common mode remain unpriced. Stronger-tone demands reuse these same capacitors.')
                # Preferred mapping: price explicit plate-area caps instead of
                # treating the minimum-current point as a minimum-area result.
                if tuple(order)==(2,1,0) and tuple(pairing)==(0,1):
                    trade=[]
                    for density_ff in (.9,1.8):
                        for plate_mm2 in (.6,1.2):
                            max_units=plate_mm2*density_ff*1e-9/(2*unit_c)
                            area_vector=np.r_[np.zeros(5),np.ones(5)/max_units]
                            constrained=optimize.minimize(lambda x:float(objective_weights@x),passive.x,
                                jac=lambda x:objective_weights,bounds=[(1.,None)]*10,method='SLSQP',
                                constraints=[dict(type='ineq',fun=lambda x:1-M@(1/x[:5])-MR@(1/x[5:]),
                                    jac=lambda x:np.c_[M/x[None,:5]**2,MR/x[None,5:]**2]),
                                    dict(type='ineq',fun=lambda x:1-area_vector@x,jac=lambda x:-area_vector)],
                                options=dict(ftol=1e-9,maxiter=500))
                            noise_ratio=float(max(M@(1/constrained.x[:5])+MR@(1/constrained.x[5:])))
                            area_ratio=float(area_vector@constrained.x)
                            feasible=bool(constrained.success and noise_ratio<=1+1e-7 and area_ratio<=1+1e-7)
                            trade.append(dict(density_ff_per_um2=density_ff,plate_limit_mm2=plate_mm2,
                                feasible_allocation_found=feasible,solver_message=constrained.message,
                                maximum_noise_budget_ratio=noise_ratio,plate_limit_ratio=area_ratio,
                                per_integrator_gm_s=(minimum*constrained.x[:5]).tolist() if feasible else None,
                                integration_cap_per_iq_f=(unit_c*constrained.x[5:]).tolist() if feasible else None,
                                paired_filter_current_a=float(objective_weights@constrained.x*.001) if feasible else None,
                                remaining_support_a=float(support-objective_weights@constrained.x*.001) if feasible else None))
                    entry['rc_noise_and_capacitive_drive']['plate_constrained_candidates']=trade
                rc=entry['rc_noise_and_capacitive_drive']
                load=np.asarray(swings[0]['resistor_absolute_current_per_cap_a_per_f'])
                rc['separate_resistor_drive_reservation_a']=float(2*load@integration_c)
                rc['current_with_separate_resistor_drive_reservation_a']=float(input_bias+drive_bias+2*load@integration_c)
                rc['resistor_drive_scope']='Conservative sum of independent branch peak currents into ideal virtual-ground summers, using existing sizes and the first tone stimulus. Separate class-A reservation, not measured consumption or a necessary minimum: shared drivers, phase cancellation and class-AB operation can change cost. Does not include numerator summer implementation or finite virtual-ground errors. No reoptimization.'
                for candidate in rc.get('plate_constrained_candidates',[]):
                    if candidate['feasible_allocation_found']:
                        extra=float(2*load@np.asarray(candidate['integration_cap_per_iq_f']))
                        candidate['separate_resistor_drive_reservation_a']=extra
                        candidate['current_with_separate_resistor_drive_reservation_a']=candidate['paired_filter_current_a']+extra
                        allocated_area=sum(architecture['blocks'][name]['resource_allocation']['area_ceiling_um2']
                                           for name in ('rxfilter_i','rxfilter_q'))/1e6
                        candidate['remaining_filter_circuit_area_mm2']=allocated_area-candidate['plate_limit_mm2']
                        candidate['fits_current_and_plate_allocation']=bool(
                            candidate['current_with_separate_resistor_drive_reservation_a']<=support and
                            candidate['plate_limit_mm2']<allocated_area)
                        candidate['physical_qualification']=False
                costs.append(entry)
            rows.append(dict(order=list(order),zero_pairing=list(pairing),signal_enbw_hz=signal_bw,
                independent_integrator_noise_enbw_hz=noise_bw.tolist(),noise_names=m['noise_names'],
                observer_names=m['observer_names'],tone_headroom=swings,noise_bandwidth_bias=costs))
    owner_audit=owner_current_gate(contract,architecture,design=design)
    return dict(design_provenance=design.provenance(),operating_conditions=conditions,
        model_role='shared_design_analytical_filter_allocation',
        diagnostic_assumptions=dict(input_gain=10.,noise_figure_goal_db=6.,
            maximum_input_gain_rail_v=3.6,minimum_headroom_rail_v=2.5,
            nominal_node_headroom_v=.8,external_insertion_loss_db=2.,
            integrator_ratio=32.,retune_ratio=32.,blocker_offset_hz=12e6),
        owner_reconciliation=owner_audit,cases=rows,cutoff_hz=cutoff,integrator_ratio=32.,retune_ratio=32.,paired_rx_filter_budget_a=support,
        noise_frequency_grid_hz=(nf_grid*cutoff).tolist(),
        basis='Unity-DC real pole plus two LP/BP state-variable notch sections; permutations are design-time alternatives, not new routing controls. Integrator noise sources are independent real one-sided voltage densities. ENBW=rate*C*P*C.T/2 with A*P+P*A.T=-B*B.T. Total NF=6 dB is partitioned between a 3/5 dB frontend and filter, rather than counted twice. Noise gain and node headroom use the existing 2.5 V floor; tone excitation separately uses the 3.6 V model ceiling to avoid cancelling stored high-gain excitation against low-rail headroom. This is a separated-rail screen, not a simulated rail transition. Illustrative e_n^2=4*k*T*gamma/gm and gm>=2*pi*fp*C_min; minimum summed gm satisfies the integrated and 401 sampled passband noise constraints. Required C=gm/(2*pi*fp) increases when noise forces higher gm, keeping the shared-bandwidth hypothesis consistent. Currents include two I/Q copies.',
        scope='Voltage-scaled linear mathematical candidate, not transistor design. Outer noise_bandwidth_bias fields are amplifier-drive-noise-only comparisons. Nested rc_noise_and_capacitive_drive adds explicit summing-resistor noise, integration capacitors and a separate class-A capacitive-drive hypothesis. Mirrors, actual resistor-driver implementation, complete amplifier voltage-noise gain, excess/flicker noise, finite DC gain, common mode, nonlinear internal swing and additional poles remain absent. Uniform effective bandwidth and ideal coefficient retuning. Sampled NF lacks an inter-frequency enclosure and does not establish complete receiver NF, EVM or sensitivity. Required compensation capacitance is an unpriced implementation obligation. Sampled steady-tone node peaks omit OFDM crest factor, switching histories and feedback of saturation. Paired RX-filter costs are compared with their current block allocation, excluding budgets owned by other RF blocks. Exceeding it rejects that scenario; a smaller cost does not prove physical fit.')


def rf_chain_case(contract,architecture,name,*,design=None,rejection_context=None):
    """First joined impairment matrix: explicit conditional cases, not compliance."""
    import math
    import numpy as np
    from converter_dynamics import parameters_from_inventory
    from selected_rf import minimum_envelope_oversample,wideband_transmit,receive_supply_reference
    from wideband_packet import run_acquisition_case
    definitions={
        'wideband_nominal':('wideband',-65.,-30.,False),
        'wideband_weak':('wideband',-75.,-30.,False),
        'wideband_gain36':('wideband',-65.,-30.,False),
        'wideband_weak_gain36':('wideband',-75.,-30.,False),
        'wideband_mid_gain36':('wideband',-70.,-30.,False),
        'wideband_gain36_rf_corner':('wideband',-65.,-30.,True),
        'narrowband_rf_corner':('narrowband',-67.,-50.,True),
        'wideband_adverse':('wideband',-65.,-30.,True),
        'wideband_failure_control':('wideband',-85.,-30.,False),
        'narrowband_nominal':('narrowband',-67.,-50.,False),
        'narrowband_weak':('narrowband',-75.,-50.,False),
        'narrowband_adverse':('narrowband',-67.,-50.,True),
        'narrowband_failure_control':('narrowband',-80.,-50.,False),
        'tx_nominal':('tx',0.,0.,False),
        'tx_adverse':('tx',0.,0.,True),
    }
    if name not in definitions:raise ValueError('Unknown RF chain case')
    mode,wanted,blocker,adverse=definitions[name]
    carrier=2.426e9
    if design is None:design=DesignDefinition.from_documents(contract,architecture)
    elif design.contract!=contract or design.architecture!=architecture:
        raise ValueError('RF chain documents conflict with supplied design snapshot')
    if adverse and mode!='tx':
        changes={
            'blocks.lna.parameters.noise_figure_db':architecture['blocks']['lna']['parameters']['noise_figure_db']+2.,
            'blocks.lna.parameters.iip3_dbm':architecture['blocks']['lna']['parameters']['iip3_dbm']-3.}
        if not name.endswith('rf_corner'):
            changes['model_assumptions.paired_sar_comparator.parameters.tau_s']=100e-12
        if mode=='wideband':
            changes.update({f'blocks.pga_{lane}.parameters.gain_response_tau_s':2e-6
                            for lane in ('i','q')})
        design=design.hypothetical(reason='Assigned adverse RF conversion-chain corner',changes=changes)
        architecture=design.architecture
    settings=dict(engine='rf',direction='tx' if mode=='tx' else 'rx',reference_hz=carrier,sample_divider=64)
    if mode=='tx':settings['tx_gain']=5.72
    if mode!='tx':settings['pga_gain_db']=39. if mode=='narrowband' else 36. if 'gain36' in name else max(architecture['blocks']['pga_i']['parameters']['gain_db'])
    if rejection_context is not None:
        rejection_context.clear()
        rejection_context.update(name=name,mode=mode,design_provenance=design.provenance(),
            requested_configuration=dict(settings),resolved_configuration=None,
            configuration_resolution='not_completed',scenario_overrides=[],
            wanted_dbm=wanted,blocker_dbm=blocker,adverse=adverse)
    config=design.configure(**settings)
    scenario=Scenario(wanted_dbm=None if mode=='tx' else wanted,blocker_dbm=None if mode=='tx' else blocker)
    inventory_mode=config.inventory_mode
    row=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),scenario_stimuli=scenario.stimulus_record(),
        probe_assumptions=dict(source_phase_amplitude_scale=2. if adverse else 1.,
            reason='Assigned source/input noise stress; not a characterized process corner'),
        name=name,mode=mode,wanted_dbm=wanted,blocker_dbm=blocker,adverse=adverse,carrier_hz=carrier)
    # Preserve the actual variant and completed resolution stages on solver errors.
    # Exceptions still propagate to callers; only the CLI turns ValueError into a report.
    if rejection_context is not None:
        rejection_context.clear();rejection_context.update(row);row=rejection_context
    raw=b.configured_environment(config,scenario)
    row.update(design_binding=dict(inventory_mode=inventory_mode,
            current_report=raw['inventory_current_report'],
            converter_parameters=raw['converter_parameters']),
        inventory_current_ma=raw['inventory_current_report']['total_ma'],
        package=dict(return_l_h=raw['network']['return_l_h'],die_esl_h=raw['network']['network']['die_esl']))
    env,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
    row['clock']=clock
    if env is None:return dict(row,accepted=False,status='clock_rejected')
    # Increase the already delivered source/input random spectrum only; keep
    # package-induced timing, current and local threshold feedback unchanged.
    scale=2. if adverse else 1.
    env=dict(env,delivered_phase_tones=tuple((f,a*scale,p) for f,a,p in env['delivered_phase_tones']))
    tones=env['delivered_phase_tones']
    row['lo_noise']=dict(amplitude_scale=scale,integrated_random_phase_rms_rad=math.sqrt(sum(a*a/2 for f,a,p in tones)),
        tones=tones,scope='Finite assigned source/input spectrum; package-driven phase added by DeliveredClock. Doubled amplitude is +6.02dB phase-noise power, not a measured process corner.')
    nf=architecture['blocks']['lna']['parameters']['noise_figure_db']
    iip3=architecture['blocks']['lna']['parameters']['iip3_dbm']
    codes=tuple(architecture['blocks']['pga_i']['parameters']['gain_db'])
    sar=parameters_from_inventory(architecture)
    comparator=architecture['model_assumptions']['paired_sar_comparator']['parameters']
    row['impairments']=dict(noise_figure_db=nf,input_iip3_dbm=iip3,comparator=comparator,
        converter_aperture_rms_s=architecture['model_assumptions']['paired_adc']['parameters']['aperture_rms_s'],external_insertion_loss_db=2.)
    if mode=='wideband':
        result=run_acquisition_case(env,431,start_sample=137,carrier_offset_hz=-120e3,
            payload_bytes=16,oversample=max(256,b.minimum_envelope_oversample(env)),
            wanted_dbm=wanted,blocker_dbm=blocker,gain_db=36. if "gain36" in name else max(codes),gain_codes_db=codes,
            noise_figure_db=nf,input_iip3_dbm=iip3,sar_parameters=sar,comparator_model=comparator,
            gain_initial_db=30.,gain_command_s=2e-6)
        rx=result['analog']['receiver'];gain=rx['gain_cases'][0]
        checks=dict(payload=result['payload_correct'],feedback=result['analog']['numerical_feedback_converged'],
            rail_domain=min(rx['observed_rail_interval_v'])>=2.5 and max(rx['observed_rail_interval_v'])<=3.6,
            pga_not_clipped=gain['pga_clipped_samples_during_source']==0,
            frontend_model_valid=rx['frontend_nonlinearity']['within_assigned_small_compression_range'],
            reference_current=gain['adc']['reference_with_bias_peak_a']<=architecture['blocks']['refbuf']['resource_allocation']['current_budget_ma']['rf_rx']/1000,
            adc_headroom=rx['pga_nominal_peak_limit_v']*max(rx['observed_rail_interval_v'])/receive_supply_reference(env,'headroom_reference_v')<min(gain['adc']['reference_interval_v']))
        row.update(receiver=result,checks=checks,accepted=all(checks.values()))
    elif mode=='narrowband':
        steps=max(256,minimum_envelope_oversample(env,sample_hz=carrier/64,guard_hz=3.1e6))
        options=dict(lo_divider=64,noise_figure_db=nf,input_iip3_dbm=iip3,
            rx_cutoff_hz=.5e6,rx_filter_family='rx_finite_zero',converter_bits=architecture['blocks']['adc_i']['parameters']['native_bits'],
            initial_gain_db=39.,maximum_gain_db=max(codes),gain_codes_db=codes,
            aperture_rms_s=architecture['model_assumptions']['paired_adc']['parameters']['aperture_rms_s'],dynamic_rail=True,sar_parameters=sar,
            comparator_model=comparator,mixer_substeps=steps)
        rx,retained=b.coupled_scan_request(env,contract,rx_options=options,
            stimulus=dict(seed=81,wanted_dbm=wanted,blocker_dbm=blocker,blocker_modulation='gfsk_prbs15'),
            progress=lambda step:print(name,'feedback',step['iteration'],step['correct_request'],flush=True))
        rails=rx['converter']['evaluated_supply_interval_v']
        checks=dict(payload=rx['correct_request'],feedback=rx['reference_feedback']['numerical_feedback_converged'],
            rail_domain=min(rails)>=2.5 and max(rails)<=3.6,pga_not_clipped=rx['gain_control']['pga_clipped_samples']==0,
            frontend_model_valid=rx['frontend_nonlinearity']['within_assigned_small_compression_range'],
            reference_current=rx['converter']['reference_with_bias_peak_a']<=architecture['blocks']['refbuf']['resource_allocation']['current_budget_ma']['rf_rx']/1000,
            adc_headroom=rx['pga_nominal_peak_limit_v']*max(rails)/receive_supply_reference(env,'headroom_reference_v')<min(rx['converter']['reference_interval_v']))
        row.update(receiver=rx,checks=checks,accepted=all(checks.values()))
        if checks['payload'] and checks['feedback']:
            tx_config=design.configure(engine='rf',direction='tx',reference_hz=carrier,sample_divider=64)
            tx_raw=b.configured_environment(tx_config,scenario)
            tx_env,tx_clock=b.reference_payload_environment(tx_raw,dict(link_r_ohm=1e-5),False)
            row.update(tx_resolved_configuration=tx_config.record(),tx_clock=tx_clock,
                tx_design_binding=dict(inventory_mode=tx_config.inventory_mode,
                    current_report=tx_raw['inventory_current_report']),
                exchange_scope='Independently settled RX and TX configurations from one design; no retained analog turnaround or reference-charge handoff.')
            if tx_env is None:
                tx=dict(transmitted=False,reason='TX clock rejected',design_provenance=design.provenance(),
                    resolved_configuration=tx_config.record())
            else:
                tx_env=dict(tx_env,delivered_phase_tones=tuple((f,a*scale,p) for f,a,p in tx_env['delivered_phase_tones']))
                tx=b.transmitted_scan_response(rx,tx_env,contract,mixer_substeps=steps,
                    reconstruction_order=3,dynamic_rail=True,rf_bias_a=tx_clock['ledger']['owner_current_a']['rf'],
                    nominal_gain=tx_config.resolved_tx_gain,
                    pad_series_ohm=2*architecture['blocks']['rftxpad']['parameters']['series_r_ohm_per_leg'],
                    rf_load=dict(bond_series_ohm=.4,bond_loop_h=8e-9,
                        differential_cap_f=architecture['blocks']['rftxpad']['parameters']['capacitance_f_per_leg']/2,
                        series_match_f=(1.1 if adverse else 1.)/((2*math.pi*carrier)**2*8e-9)))
            row['transmitter']=tx
            row['tx_checks']=dict(transmitted=tx.get('transmitted',False),peer_decode=tx.get('peer_correct_response',False),
                rail_domain=tx.get('evaluated_supply_valid',False),electrical=tx.get('electrical',{}).get('within_declared_compliance',False),
                mixer_headroom=tx.get('mixer_input_complex_peak_v',float('inf'))<=architecture['blocks']['txmix_i']['parameters']['maximum_input_complex_peak_v'])
            row['exchange_accepted']=row['accepted'] and all(row['tx_checks'].values())
    else:
        driver=architecture['blocks']['rfdriver']['parameters']
        gain=config.resolved_tx_gain
        inductance=8e-9;cap=1/( (2*math.pi*carrier)**2*inductance)
        network=dict(bond_series_ohm=.4,bond_loop_h=inductance,
            differential_cap_f=architecture['blocks']['rftxpad']['parameters']['capacitance_f_per_leg']/2,
            series_match_f=cap*(1.1 if adverse else 1.))
        tx=wideband_transmit(env,oversample=max(256,b.minimum_envelope_oversample(env)),
            cutoff_hz=max(architecture['blocks']['txfilter_i']['parameters']['cutoff_hz']),
            input_rms_codes=250.,nominal_gain=gain,rf_load=network,
            pad_series_ohm=2*architecture['blocks']['rftxpad']['parameters']['series_r_ohm_per_leg'])
        power=10*math.log10(tx['loaded_average_active_power_w']/1e-3)
        checks=dict(electrical=tx['electrical']['within_declared_compliance'],
            mixer_headroom=tx['mixer_input_complex_peak_v']<=architecture['blocks']['txmix_i']['parameters']['maximum_input_complex_peak_v'],
            host_not_clipped=tx['host_input_clipped_components']==0,driver_not_clipped=tx['driver_current_clipped_samples_during_source']==0,
            diagnostic_bpsk=tx['observation']['bpsk_errors']==0,
            rail_domain=min(tx['observed_rail_interval_v'])>=2.5 and max(tx['observed_rail_interval_v'])<=3.6,
            target_power=power>=driver['target_mean_power_dbm'])
        row.update(transmitter=tx,loaded_mean_power_dbm=power,checks=checks,accepted=all(checks.values()))
    row['status']='conditional_operating_point' if row['accepted'] else 'failed_operating_point'
    return row


def revision_reply_environment(design,carrier,return_l,die_esl,steps):
    config=design.configure(engine='rf',direction='tx',reference_hz=carrier,sample_divider=64)
    scenario=Scenario().override(reason='BLE reply package comparison',
        package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
    raw=b.configured_environment(config,scenario)
    environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=-1.)
    parameters=design.architecture['blocks']['dac_i']['parameters']
    options=dict(mixer_substeps=steps,converter_bits=parameters['native_bits'],reconstruction_order=None,
        aperture_rms_s=design.architecture['model_assumptions']['paired_dac']['parameters']['aperture_rms_s'],
        dynamic_rail=True,rf_bias_a=raw['inventory_current_a']['rf'])
    context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
        scenario_overrides=scenario.record(),clock=clock,
        transition_scope='Independent settled TX environment at absolute reply time; RX feedback history is not carried across. No continuous RX-to-TX transition qualification.')
    return environment,options,context


def revision_ble_options(environment,steps):
    options=b.receiver_inventory_options(environment)
    config=environment['resolved_configuration']
    options.update(lo_divider=config['sample_divider'],initial_gain_db=config['pga_gain_db'],
        blocker_offsets_hz=(2e6,),rx_cutoff_hz=.5e6,aperture_rms_s=environment['adc_noise_parameters']['aperture_rms_s'],
        dynamic_rail=True,mixer_substeps=steps)
    return options


def revision_clock_environment(design,mode,carrier,*,return_l=None,die_esl=None,feed_candidate=False,sample_divider=64):
    if feed_candidate:
        design=design.hypothetical(reason='Revision-check feed-resistance candidate',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':1.})
    scenario=Scenario();overrides={}
    if return_l is not None:overrides['package_return_inductance_h']=return_l
    if die_esl is not None:overrides['die_decoupling_esl_h']=die_esl
    if overrides:scenario=scenario.override(reason='Revision-check package comparison',**overrides)
    if mode=='wire':
        config=design.configure(engine='wire',direction='tx',reference_hz=carrier,host_divider=8)
        environment=b.configured_environment(config,scenario)
        context=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
            scenario_overrides=scenario.record())
    else:
        environment,context=b.clock_screen_environment(design,mode,carrier,scenario=scenario,sample_divider=sample_divider)
    environment['probe_context']=context
    return environment,context


def configured_forwarded_clock_screen(design):
    """Loaded shared REF input through retained PLL loss and requalification."""
    cases=[]
    for pixel,divider in ((74.25e6,4),(148.5e6,8)):
        for fractional in (1.,1.001):
            config=design.configure(engine='wire',direction='tx',reference_hz=pixel/fractional,
                clock_source='forwarded_word',host_divider=divider)
            clock=b.configured_forwarded_clock(config,Scenario(reference_peak_v=.5))
            pll=clock.pll
            before=clock.advance(1e-6)
            acquired=clock.advance(21e-6)
            phase=clock.output_phase_cycles
            clock.set_source(False,22e-6)
            lost=not clock.advance(24e-6)
            retained=clock.output_phase_cycles>phase
            clock.set_source(True,24e-6)
            early=clock.advance(25e-6)
            restored=clock.advance(45e-6)
            rejection=None
            try:b.configured_forwarded_clock(config,Scenario(reference_peak_v=1.))
            except ValueError as error:rejection=str(error)
            checks=dict(no_early_readiness=not before,acquired=acquired,loss_revokes=lost,
                phase_continues_while_unqualified=retained,no_early_recovery=not early,
                recovered=restored,retained_pll=clock.pll is pll,
                excessive_source_rejected=rejection=='Reference input envelope rejected')
            cases.append(dict(resolved_configuration=config.record(),reference_input=clock.reference_input.report,
                checks=checks,passed=all(checks.values()),source_epoch=clock.source_epoch,
                detector_observations=clock.pll.detector_updates,
                final_frequency_error_ppm=(clock.output_hz/config.line_rate_bps-1)*1e6,
                rejected_source_reason=rejection))
    return dict(passed=all(c['passed'] for c in cases),cases=cases,
        scope='Four configured timing points with stationary shared differential pad/package forcing and finite edge windows. Input-presence loss is an injected observation; source-removal electrical transients, continuous lane FIFO/pad traffic and cross-chip alignment are separate lifecycle obligations.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--forwarded-clocks',action='store_true',help='Shared loaded fractional video clocks with retained PLL recovery')
    group.add_argument('--wifi-exchanges',action='store_true',help='Selected FPGA correction, DAC noise and retained Wi-Fi exchanges')
    parser.add_argument('--reference-tools',help='Pinned independent Wi-Fi tools checkout for --wifi-exchanges')
    group.add_argument('--rf-chain-case',choices=('wideband_nominal','wideband_weak','wideband_gain36','wideband_weak_gain36','wideband_mid_gain36','wideband_gain36_rf_corner','narrowband_rf_corner','wideband_adverse','wideband_failure_control','narrowband_nominal','narrowband_weak','narrowband_adverse','narrowband_failure_control','tx_nominal','tx_adverse'))
    group.add_argument('--usb-trim-envelope',action='store_true',help='Fast inverse current-trim/load/supply screen')
    group.add_argument('--usb-common-packet',action='store_true',help='USB packet with common host/package supply forcing')
    group.add_argument('--cdr-cold',action='store_true',help='Independent nominal local clock acquisition and held-out tracking')
    group.add_argument('--cdr-selected',action='store_true',help='Selected shared periodic-tracking acceptance on two independent trajectories')
    group.add_argument('--cdr-window-screen',action='store_true',help='Coarse phase-window candidate with extra current and loading stress')
    group.add_argument('--cdr-detector-screen',action='store_true',help='Two-cycle three-sample early/late detector experiment; readiness remains unqualified')
    group.add_argument('--cdr-slope-screen',action='store_true',help='Two-cycle slope-predictor candidate with exact transition gaps')
    group.add_argument('--cdr-observed-bound',action='store_true',help='Full SSC/gap screen with observation-derived holdover uncertainty')
    group.add_argument('--cdr-aperture-screen',action='store_true',help='Full-cycle candidate with reduced local supply-to-aperture coupling')
    group.add_argument('--cdr-full-cycle',action='store_true',help='Matched two-cycle SSC and transition-gap loop comparison')
    group.add_argument('--cdr-tuning',action='store_true',help='Short shared-supply CDR loop/noise tradeoff')
    group.add_argument('--rf-output-load',action='store_true',help='Fast RF pad/bond load and existing gain-range screen')
    group.add_argument('--common-tx',action='store_true',help='Transmit power/quality using selected common inventory')
    group.add_argument('--shared-pad',action='store_true',help='Connected shared-pad and protection envelope without payload reruns')
    group.add_argument('--common-wideband',action='store_true',help='Wideband acquisition using selected inventory and converter')
    group.add_argument('--common-rf',action='store_true',help='Real RF packet using the common current/package catalog')
    parser.add_argument('--tx-signal-loop-nh',type=float,help='Differential RF signal-bond loop inductance hypothesis')
    parser.add_argument('--tx-series-match-pf',type=float,help='External differential series matching capacitance hypothesis')
    parser.add_argument('--tx-gain',type=float,help='Existing driver gain request, quantized to its selected8-bit range')
    parser.add_argument('--tx-rms-codes',type=float,default=180.,help='FPGA complex RMS transport-code request for --common-tx')
    parser.add_argument('--wideband-wanted-dbm',type=float,default=-85.,help='Wanted RF level for --common-wideband; gain remains inventory-limited')
    parser.add_argument('--rf-filter',choices=('rx_finite_zero','rx_all_pole_control'),default='rx_finite_zero',help='Generic RF filter coefficients for --common-rf')
    group.add_argument('--converter-timing',action='store_true',help='Coupled converter loading and asynchronous timing screen')
    group.add_argument('--common-envelope',action='store_true',help='Shared inventory-current/package/clock preflight for RF and wired')
    group.add_argument('--owner-current-gate',action='store_true',help='Current block-to-rail allocations and selected mode ceilings')
    group.add_argument('--tx-load-numerics',action='store_true',help='Short current-transition grid and guard separation')
    group.add_argument('--wired',action='store_true')
    group.add_argument('--rf',action='store_true')
    group.add_argument('--adc-rf',action='store_true',help='Matched wideband RX with added budgeted ADC switching')
    group.add_argument('--rail',action='store_true',help='Coherent selected RF rail validity across package cases')
    group.add_argument('--ble-joint',action='store_true',help='Matched BLE conversion chain over package hypotheses with budgeted ADC activity')
    group.add_argument('--rx-memory',action='store_true',help='Matched all-pole/finite-zero filter history and packet acquisition')
    group.add_argument('--filter-realization',action='store_true',help='Finite integrator bandwidth, coefficient retuning and coupled wideband RX')
    group.add_argument('--host-energy-comparison',action='store_true',help='Fixed network with evidence-informed receiver energy and retained adverse case')
    group.add_argument('--host-loop-topology',action='store_true',help='Compare aggregate-scaled and explicit local capacitor-loop inductance hypotheses')
    group.add_argument('--host-selected-load',action='store_true',help='Matched package screen at selected board load and characterized output energy')
    group.add_argument('--host-output-source-evidence',action='store_true',help='Pinned public output-cell PAD energy by drive/slew condition')
    group.add_argument('--host-source-evidence',action='store_true',help='Read pinned public GF180 input-cell energy characterization')
    group.add_argument('--host-edge-network',action='store_true',help='Fixed-network finite host-current edge convergence')
    group.add_argument('--filter-budget',action='store_true',help='Biquad ordering, internal headroom and noise/bandwidth current allocation')
    group.add_argument('--ble',action='store_true',help='Selected-channel BLE CW versus modulated blocker diagnostic')
    group.add_argument('--input-envelope',action='store_true',help='Fast independent return-inductance/decoupling-ESL voltage screen')
    parser.add_argument('--feed-candidate',action='store_true',help='1 ohm feed, 0.25 nH return, twice internal pulses')
    parser.add_argument('--lower-sensitivity',action='store_true',help='Diagnostic 0.0125 ps/mV candidate')
    parser.add_argument('--feedback',action='store_true',help='Join BLE converter-generated package/input disturbance')
    args=parser.parse_args()
    design=load_design()
    if args.feedback and not args.ble:parser.error('--feedback requires --ble')
    if args.lower_sensitivity and not args.feed_candidate:parser.error('--lower-sensitivity requires --feed-candidate')
    if args.feed_candidate and not (args.wired or args.rf):parser.error('--feed-candidate requires --wired or --rf')
    p=Path(__file__).resolve().parents[1]
    path=p/'evidence/selected-revision-check.json'
    report=json.loads(path.read_text()) if path.exists() else {}
    # Saved results are historical inputs, not prerequisites for a fresh run.
    # Never overwrite their hashes merely because the implementation changed.
    previous=report.get('sources_sha256',{})
    if 'package_clock_screen' in report and previous:
        report['package_clock_screen'].setdefault('sources_sha256',dict(previous))
    hashes=b.baseline_source_hashes()
    def verify_sources():
        if b.baseline_source_hashes()!=hashes:
            raise RuntimeError('Sources changed during selected review; previous evidence preserved')
    def write_report(path,value):
        verify_sources()
        b.write_evidence(path,value)
    if args.reference_tools and not args.wifi_exchanges:parser.error('--reference-tools requires --wifi-exchanges')
    if args.forwarded_clocks:
        result=configured_forwarded_clock_screen(design)
        report['configured_forwarded_clocks']=dict(result,sources_sha256=hashes)
        write_report(path,report)
        print(json.dumps(result,indent=2))
        if not result['passed']:raise SystemExit(1)
        return
    if args.cdr_cold:
        result=selected_cdr_tracking_screen(design,cold=True)
        report["selected_cdr_cold"]=dict(sources_sha256=hashes,result=result,passed=result["selected_tracking_pass"])
        write_report(path,report)
        print(json.dumps(dict(passed=bool(result["selected_tracking_pass"]),
            first_qualified_bit=int(result["result"]["cases"][0]["first_qualified_bit"]) if result["result"]["cases"][0]["first_qualified_bit"] is not None else None,
            peak_residual_ppm=float(result["result"]["cases"][0]["heldout_free_run_residual_abs_ppm_quantiles"][-1])),indent=2))
        if not result["selected_tracking_pass"]:raise SystemExit(1)
        return
    if args.cdr_selected:
        results=[selected_cdr_tracking_screen(design,source_seed=seed,source_phase_cycles=phase)
                 for seed,phase in ((9024,.217),(9025,.317))]
        report['selected_cdr_tracking']=dict(sources_sha256=hashes,results=results,
            passed=all(r['selected_tracking_pass'] for r in results))
        write_report(path,report)
        print(json.dumps(dict(passed=report['selected_cdr_tracking']['passed'],
            peak_residual_ppm=[float(r['result']['cases'][0]['heldout_free_run_residual_abs_ppm_quantiles'][-1]) for r in results]),indent=2))
        if not report['selected_cdr_tracking']['passed']:raise SystemExit(1)
        return
    if args.wifi_exchanges:
        result=selected_wifi_exchange_screen(design,reference_tools=args.reference_tools)
        report['selected_wifi_exchanges']=dict(result=result,sources_sha256=hashes)
        write_report(path,report)
        print(json.dumps(dict(mcs_completed=[r['completed'] for r in result['diagnostic_mcs']],
            retained_completed=result['retained_exchange']['completed'],
            independent_legacy_completed=None if result['independent_legacy'] is None else result['independent_legacy']['completed'])))
        return
    if args.rf_chain_case:
        rejection_context=dict(name=args.rf_chain_case,design_provenance=design.provenance(),
            resolved_configuration=None,scenario_overrides=[],configuration_resolution='not_completed')
        try:
            result=rf_chain_case(design.contract,
                design.architecture,args.rf_chain_case,design=design,rejection_context=rejection_context)
        except ValueError as error:
            result=dict(rejection_context,accepted=False,status='model_rejected',reason=str(error))
        verify_sources()
        report.setdefault('rf_chain_first_version',dict(scope='Conditional combined RF impairment points on selected inventory/package. Not PER, standards compliance, proven GF180 performance or a continuous uncertainty enclosure.',cases={}))['cases'][args.rf_chain_case]=dict(result,sources_sha256=hashes)
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        print(args.rf_chain_case,result['status'],result.get('checks'),flush=True)
        return
    if args.cdr_window_screen or args.cdr_detector_screen or args.cdr_slope_screen or args.converter_timing or args.usb_trim_envelope or args.usb_common_packet or args.cdr_tuning or args.cdr_full_cycle or args.cdr_aperture_screen or args.cdr_observed_bound or args.common_envelope or args.common_rf or args.common_wideband or args.shared_pad or args.common_tx or args.rf_output_load:
        if args.converter_timing:
            result=converter_timing_screen(design.contract,
                design.architecture,design=design)
            verify_sources()
            report['converter_timing_envelope']=dict(result,sources_sha256=hashes)
            write_report(path,report)
            return
        if args.usb_trim_envelope:
            validate_saved_design_input(report['usb_common_packet'],design,engine='wire',direction='duplex')
            report['usb_trim_envelope']=dict(usb_trim_envelope(report['usb_common_packet'],design.architecture),sources_sha256=hashes)
            write_report(path,report)
            return
        if args.usb_common_packet:
            result=usb_common_packet_screen(design.contract,
                design.architecture,design=design)
            verify_sources()
            report['usb_common_packet']=dict(result,sources_sha256=hashes)
            write_report(path,report)
            return
        if args.cdr_window_screen or args.cdr_detector_screen or args.cdr_slope_screen or args.cdr_tuning or args.cdr_full_cycle or args.cdr_aperture_screen or args.cdr_observed_bound:
            screen=cdr_full_cycle_screen if args.cdr_window_screen or args.cdr_detector_screen or args.cdr_slope_screen or args.cdr_full_cycle or args.cdr_aperture_screen or args.cdr_observed_bound else cdr_tuning_screen
            result=screen(design.contract,
                                     design.architecture,design=design,
                                     **({'window_screen':True} if args.cdr_window_screen else {'detector_screen':True} if args.cdr_detector_screen else {'slope_screen':True} if args.cdr_slope_screen else {'observed_bound':True} if args.cdr_observed_bound else {'aperture_screen':True} if args.cdr_aperture_screen else {}))
            verify_sources()
            report['cdr_windowed_detector' if args.cdr_window_screen else 'cdr_detector_screen' if args.cdr_detector_screen else 'cdr_slope_screen' if args.cdr_slope_screen else 'cdr_observed_bound' if args.cdr_observed_bound else 'cdr_aperture_screen' if args.cdr_aperture_screen else 'cdr_full_cycle' if args.cdr_full_cycle else 'cdr_tuning']=dict(result,sources_sha256=hashes)
            write_report(path,report)
            return
        if args.rf_output_load:
            architecture=design.architecture
            baseline=report['common_envelope']['transmitter_cases']['250.0']
            validate_saved_design_input(baseline,design,engine='rf',direction='tx')
            result=rf_output_load_screen(architecture,baseline)
            report['rf_output_load']=dict(result,sources_sha256=hashes)
            write_report(path,report)
            return
        if args.shared_pad:
            result=shared_pad_design_screen(design)
            verify_sources()
            report['shared_pad_envelope']=dict(result,sources_sha256=hashes)
            write_report(path,report)
            return
        run=(common_rf_packet_screen if args.common_rf else common_wideband_packet_screen if args.common_wideband
             else common_tx_screen if args.common_tx else common_envelope_screen)
        result=run(design.contract,
                                      design.architecture,design=design,
                                      **({'filter_family':args.rf_filter} if args.common_rf else
                                         {'wanted_dbm':args.wideband_wanted_dbm} if args.common_wideband else
                                         {'input_rms_codes':args.tx_rms_codes,'signal_loop_nh':args.tx_signal_loop_nh,
                                          'series_match_pf':args.tx_series_match_pf,'driver_gain':args.tx_gain} if args.common_tx else {}))
        verify_sources()
        if args.common_tx:
            envelope=report.setdefault('common_envelope',{})
            cases=envelope.setdefault('transmitter_cases',{})
            old=envelope.pop('transmitter',None)
            if old is not None:cases[str(old['transmitter']['input_rms_codes'])]=old
            key=str(args.tx_rms_codes) if args.tx_signal_loop_nh is None and args.tx_gain is None else f'{args.tx_rms_codes}/gain{result["transmitter"]["nominal_gain"]}/L{args.tx_signal_loop_nh}/C{args.tx_series_match_pf}'
            cases[key]=dict(result,sources_sha256=hashes)
        elif args.common_wideband:
            envelope=report.setdefault('common_envelope',{})
            cases=envelope.setdefault('wideband_cases',{})
            old=envelope.pop('wideband_packet',None)
            if old is not None:cases[str(old['wanted_dbm'])]=old
            cases[str(args.wideband_wanted_dbm)]=dict(result,sources_sha256=hashes)
        elif args.common_rf:
            envelope=report.setdefault('common_envelope',{})
            envelope.pop('rf_packet',None)  # Superseded fixture allowed an unsupported 60 dB PGA.
            envelope.setdefault('rf_filter_cases',{})[args.rf_filter]=dict(result,sources_sha256=hashes)
        else:
            packet=report.get('common_envelope',{}).get('rf_filter_cases')
            wideband=report.get('common_envelope',{}).get('wideband_cases')
            transmitter=report.get('common_envelope',{}).get('transmitter_cases')
            report['common_envelope']=dict(result,sources_sha256=hashes)
            if packet is not None:report['common_envelope']['rf_filter_cases']=packet
            if wideband is not None:report['common_envelope']['wideband_cases']=wideband
            if transmitter is not None:report['common_envelope']['transmitter_cases']=transmitter
        write_report(path,report)
        return
    if args.tx_load_numerics:
        result=tx_load_numerics(design.contract,design=design)
        result['sinusoidal_controls']=tx_current_tone_controls(design.contract,design=design)
        result['native_continuation']=native_current_continuation(design.contract,design=design)
        verify_sources()
        report['tx_load_numerics']=dict(result,sources_sha256=hashes)
        write_report(path,report)
        return
    if args.feed_candidate:
        path=p/'evidence/feed-candidate-check.json'
        report=json.loads(path.read_text()) if path.exists() else {}
    c=design.contract;rows=[]
    if args.owner_current_gate:
        result=owner_current_gate(c,design=design);result['sources_sha256']=hashes
        report['owner_current_gate']=result;write_report(path,report);print(json.dumps(result,indent=2));return
    if args.adc_rf:
        from wideband_packet import run_acquisition_case
        from selected_rf import minimum_envelope_oversample
        for active in (False,True):
            raw,context=revision_clock_environment(design,'rf',2.4e9)
            mean=b.adc_pair_current_allocation(raw) if active else 0.
            raw['adc_switching']=dict(sample_hz=2.4e9/64,mean_a=mean,pulse_tau_s=.2e-9,harmonics=128)
            e,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=-1.)
            row=dict(context,adc_switching=raw['adc_switching'],clock=clock)
            if e is not None:
                row['rf']=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,
                    transmit=True,oversample=minimum_envelope_oversample(e))
                assert row['rf']['transmitted'], 'Matched RF comparison requires a wanted signal'
                print('ADC RF',mean,row['rf']['payload_correct'],row['rf']['raw_bit_errors'],flush=True)
            rows.append(row)
        verify_sources()
        report['package_adc_rf_screen']=dict(cases=rows,sources_sha256=hashes,
            scope='Matched 2.4 GHz wideband RX at selected 0.25 nH package, negative supply-delay sign, seed 431 and fixed origins. Equal-charge ADC switching uses the current ADC pair allocation, replacing its steady current at the lumped CORE/CONV node; all other owners remain reserved. Same full-network periodic rail/input forcing and causal SAR/reference-recharge feedback used by receiver. Diagnostic HE DATA with legacy training, not complete HE PPDU or PER/compliance. Prescribed periodic switching does not follow perturbed conversion event times or codes; no lifecycle or TX qualification.')
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.rail:
        for label,ret,esl in b.network_cases(design):
            raw,context=revision_clock_environment(design,'rf',2.426e9,return_l=ret,die_esl=esl)
            e,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
            row=dict(context,network_case=label,clock=clock)
            if e is not None:
                dc=e['ledger']['local_payload_clock_core_rail_v']
                tones=e['host_spectrum']['tones']
                peak=sum(t['clock_rail_voltage_peak_v'] for t in tones)
                row['triangle_interval_v']=[dc-peak,dc+peak]
                row['coherent_rail']=b.rail_excursion(tones,dc_v=dc,samples_per_fastest_period=8)
                print('rail',label,row['coherent_rail']['sampled_interval_v'],flush=True)
            rows.append(row)
        verify_sources()
        report['package_ble_rail_screen']=dict(cases=rows,sources_sha256=hashes,
            scope='Selected channel-38 periodic supply waveform, same internal pulses and differential input loading as BLE screen. One fixed set of harmonic phases. Sampled extrema plus derivative enclosure over the complete common period; triangle retained. No converter-generated transient, phase uncertainty, cold start or physical rail validation. Rejected clock cases have no downstream rail verdict.')
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.host_energy_comparison:
        source=report['host_input_library_evidence']
        charges=[('native_internal_upper',source['equivalent_average_internal_charge_per_transition_pc'][1]*1e-12),
            ('native_including_output_load_upper',source['equivalent_charge_including_output_load_pc'][1]*1e-12),
            ('adverse_unvalidated',7e-12)]
        result=dict(cases=[dict(name=name,**finite_host_edge_network_screen(receiver_charge_c=q,
            edges=(100e-12,),scales=(64,256))) for name,q in charges],
            source_evidence_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
            input_evidence=recorded_library_inputs(host_input_library_evidence=source),
            model_role='frozen_numerical_fixture',current_chip_evidence=False,
            sources_sha256=hashes,
            scope='Change only H2D receiver event energy; fixed adverse pulse shape, bank ownership, D2H drive, external return and network. Net library cycle charge is mapped to equal positive pulses as an explicit hypothesis; signed per-transition waveforms are not inferred. HOST DC reservation remains unchanged; this compares AC forcing, not measured power savings. Native TT characterization is not a custom receiver or uncertainty bound. No quiet-rail or chip feasibility verdict.')
        verify_sources()
        report['host_receiver_energy_comparison']=result;write_report(path,report);return
    if args.host_loop_topology:
        import numpy as np
        source=report['host_output_library_evidence']
        setting=next(row for row in source['cases'] if row['condition']=='!IE&OE&!PDRV0&PDRV1&!SL')
        cap=c['physical_services']['host_output']['full_rate_external_load_target_f']
        q=max(np.interp(cap*1e12,setting['load_pf'],row) for row in setting['cycle_internal_energy_pj'])/6.6*1e-12
        qin=max(report['host_input_library_evidence']['equivalent_average_internal_charge_per_transition_pc'])*1e-12
        cases=[dict(topology=label,**finite_host_edge_network_screen(receiver_charge_c=qin,
            output_cap_f=cap,output_internal_charge_c=q,local_cap_esl_h=loops,
            edges=(100e-12,),scales=(64,256))) for label,loops in
            [('aggregate_inverse_capacitance',None),('explicit_0p2nh_per_local_loop',[.2e-9]*7)]]
        report['host_loop_topology_comparison']=dict(cases=cases,sources_sha256=hashes,
            input_evidence=recorded_library_inputs(host_output_library_evidence=source,
                host_input_library_evidence=report['host_input_library_evidence']),
            model_role='frozen_numerical_fixture',current_chip_evidence=False,
            scope='Two explicit unqualified local-loop hypotheses at unchanged capacitance, ESR, branch feeds, shared return, current shapes and nominal output energy. Independent 0.2 nH loops do not preserve the former tied aggregate inductance and require actual geometry. Neither result selects a layout or bounds real package performance; no capacitance or current saving credited.')
        verify_sources()
        write_report(path,report);return
    if args.host_selected_load:
        import numpy as np
        source=report['host_output_library_evidence'];load=c['physical_services']['host_output']['full_rate_external_load_target_f']
        receiver=report['host_input_library_evidence']
        qin=max(receiver['equivalent_average_internal_charge_per_transition_pc'])*1e-12
        rows=[]
        for condition in (None,'!IE&OE&!PDRV0&PDRV1&!SL','!IE&OE&PDRV0&PDRV1&!SL'):
            cap=10e-12 if condition is None else load
            if condition is None:q=7e-12
            else:
                setting=next(row for row in source['cases'] if row['condition']==condition)
                q=max(np.interp(cap*1e12,setting['load_pf'],row) for row in setting['cycle_internal_energy_pj'])/6.6*1e-12
            rows.append(dict(condition=condition or 'historical_10pf_7pc',
                **finite_host_edge_network_screen(receiver_charge_c=qin,output_cap_f=cap,
                    output_internal_charge_c=q,edges=(100e-12,),scales=(64,256))))
        report['selected_host_load_package_comparison']=dict(cases=rows,sources_sha256=hashes,
            input_evidence=recorded_library_inputs(host_output_library_evidence=source,host_input_library_evidence=receiver),
            model_role='frozen_numerical_fixture',current_chip_evidence=False,
            source_evidence_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
            scope='Same RF-mode D2H 150 Mword/s/H2D 312.5 Mword/s and fixed historical 1 nF package hypothesis. Changes only output capacitance and nominal conditional output energy. Current shapes remain assumed: 10 mA load charging and 0.5 ns internal pulse with 100 ps smoothing. Liberty timing is not a validated current waveform; no selected 500 pF network, wired maximum-rate envelope, phase enclosure or physical qualification.')
        verify_sources()
        write_report(path,report);return
    if args.host_output_source_evidence:
        report['host_output_library_evidence']=host_output_library_evidence()
        source=report['host_input_library_evidence']
        report['host_output_library_evidence']['host_current_budget']=output_host_current_budget(c,report['host_output_library_evidence'],source)
        report['host_output_library_evidence']['input_evidence_sha256']=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
        write_report(path,report);return
    if args.host_source_evidence:
        result=host_input_library_evidence()
        report['host_input_library_evidence']=result
        write_report(path,report);return
    if args.host_edge_network:
        result=finite_host_edge_network_screen()
        verify_sources()
        report['finite_host_edge_network']=dict(result,sources_sha256=hashes)
        write_report(path,report);return
    if args.filter_budget:
        result=filter_budget_screen(c,design=design)
        verify_sources()
        report['filter_budget']=dict(result,sources_sha256=hashes)
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.filter_realization:
        result=filter_realization_screen(c,design=design)
        verify_sources()
        report['filter_realization']=dict(result,sources_sha256=hashes)
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.rx_memory:
        result=rx_memory_screen(c,design=design)
        verify_sources()
        report['rx_filter_memory']=dict(result,sources_sha256=hashes)
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.ble_joint:
        prior=report.get('package_ble_joint_screen',{})
        for old in prior.get('cases',[]):
            if 'tx_grid_guard_comparison' in old:
                report.setdefault('tx_legacy_fft_packet_control',dict(
                    comparison=old['tx_grid_guard_comparison'],sources_sha256=prior.get('sources_sha256',{}),
                    scope='Historical coarse-FFT packet discrepancy retained as the reason for native held-input propagation; not current qualification.'))
        from selected_rf import minimum_envelope_oversample
        for label,ret,esl in b.network_cases(design):
            carrier=2.426e9;sample_hz=carrier/64
            raw,context=revision_clock_environment(design,'rf',carrier,return_l=ret,die_esl=esl)
            raw['adc_switching']=dict(sample_hz=sample_hz,mean_a=b.adc_pair_current_allocation(raw),
                pulse_tau_s=.2e-9,harmonics=128)
            environment,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=-1.)
            row=dict(context,network_case=label,return_l_h=ret,die_esl_h=esl,adc_switching=raw['adc_switching'],clock=clock)
            if environment is None:row['verdict']='clock_rejected'
            else:
                steps=max(256,minimum_envelope_oversample(environment,sample_hz=sample_hz,guard_hz=3.1e6))
                options=revision_ble_options(environment,steps)
                received,reply_environment=b.coupled_scan_request(environment,c,rx_options=options,
                    stimulus=dict(seed=81,wanted_dbm=-67.,blocker_dbm=-50.,blocker_modulation='gfsk_prbs15'),
                    progress=lambda step:print('Joint BLE',label,'iteration',step['iteration'],flush=True))
                row['receiver']=received
                if received['correct_request'] and received['reference_feedback']['numerical_feedback_converged']:
                    reply_environment,tx_options,tx_context=revision_reply_environment(design,carrier,ret,esl,steps)
                    row['tx_configuration']=tx_context
                    if reply_environment is None:
                        row['transmitter']=dict(transmitted=False,reason='TX clock rejected')
                    else:
                        row['transmitter']=b.transmitted_scan_response(received,reply_environment,c,**tx_options)
                    if label==b.BASELINE_PACKAGE_CASE and reply_environment is not None:
                        capture={}
                        row['tx_current_sensitivity'],_=b.coupled_scan_reply(received,reply_environment,c,
                            tx_options=tx_options,capture_out=capture)
                        print('Joint BLE',label,'TX current native solve complete',flush=True)
                        fine={}
                        row['tx_current_tail_check'],_=b.coupled_scan_reply(received,reply_environment,c,
                            tx_options=tx_options,guard_s=4e-6,
                            initial_response=capture['response'],capture_out=fine)
                        from converter_dynamics import feedback_change
                        row['tx_native_tail_comparison']=dict(feedback_change(fine['response'],capture['response']),
                            comparison_kind='Native source sample spacing unchanged; natural zero-current tail extended from 2us to 4us. Not source-grid refinement.')
                        print('Joint BLE',label,'TX current native tail check complete',flush=True)
                    tx=row['transmitter']
                    row['warm_exchange_verdict']=('reply_not_transmitted' if not tx.get('transmitted',False) else
                        'tx_supply_outside_model_domain' if not tx['evaluated_supply_valid'] else
                        'tx_electrical_budget_failed' if not tx['electrical']['within_declared_compliance'] else
                        'conditional_peer_decode' if tx.get('peer_correct_response',False) else 'reply_failed')
                    print('Joint BLE',label,'warm reply',row['warm_exchange_verdict'],flush=True)
                # Decoding outside the converter's declared rail domain is
                # diagnostic only, even if the CRC happens to pass.
                converter=received['converter']
                valid=min(converter['evaluated_supply_interval_v'])>=2.5
                row['evaluated_supply_valid']=valid
                row['verdict']=('supply_outside_model_domain' if not valid else
                    'feedback_unresolved' if not received['reference_feedback']['numerical_feedback_converged'] else
                    'packet_failed' if not received['correct_request'] else 'conditional_single_packet_decode')
            rows.append(row);print('Joint BLE',label,row['verdict'],flush=True)
        verify_sources()
        report['package_ble_joint_screen']=dict(cases=rows,sources_sha256=hashes,
            scope='Matched channel-38 real packet and PRBS15 GFSK +2 MHz blocker, wanted -67 dBm/blocker -50 dBm before 2 dB external loss, seed 81. Package return and die ESL vary together; negative supply-delay sign, selected internal loads, dynamic rail, causal SAR and fixed-reserve recharge feedback share one environment. Selected /64 ADC sampling and assigned periodic activity use the current ADC pair allocation; FPGA converts samples to modem coordinates. This is a switching hypothesis, not measured activity. The /256 packet setting with its own ADC pulse cadence exceeds the integer-Hz/coherent-record assumptions of the fast clock screen and is not qualified by this run. Reply uses an independently settled TX inventory/clock environment at the requested absolute time; no continuous RX-to-TX state handoff is qualified. One phase/seed/offset and assigned NF/IIP3; no PER, full blocker mask, cold lifecycle join, switched bias, physical TX current characterization, launch calibration, emissions or silicon qualification.')
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.ble:
        from ble_packet import joined_scan_request
        from selected_rf import minimum_envelope_oversample
        for sign in (-1.,1.):
            raw,context=revision_clock_environment(design,'rf',2.426e9,sample_divider=256)
            raw['internal_switching_loads']=[
                dict(owner='timing',mean_a=.010,event_hz=2.426e9/16,tau_s=.2e-9,harmonics=64),
                dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
            e,clock=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=sign)
            row=dict(context,probe_assumptions=dict(aperture_rms_s=raw['adc_noise_parameters']['aperture_rms_s'],rx_cutoff_hz=.5e6),internal_switching_loads=raw['internal_switching_loads'],supply_delay_sign=sign,clock=clock,cases=[])
            if e is not None:
                steps=max(256,minimum_envelope_oversample(e,sample_hz=e['carrier_hz']/256,guard_hz=3.1e6))
                for modulation in ('cw','gfsk_prbs15'):
                    stimulus=dict(seed=81,wanted_dbm=-67.,blocker_dbm=-50.,blocker_modulation=modulation)
                    options=revision_ble_options(e,steps)
                    if args.feedback:
                        received,_=b.coupled_scan_request(e,c,rx_options=options,stimulus=stimulus,
                            progress=lambda step:print('BLE feedback',sign,modulation,step,flush=True))
                    else:received=joined_scan_request(e,c,**stimulus,**dict(b.receiver_inventory_options(e),**options))
                    row['cases'].append(received)
                    print('BLE',sign,modulation,received['correct_request'],flush=True)
            rows.append(row)
        verify_sources()
        section='package_ble_feedback_screen' if args.feedback else 'package_ble_interferer_screen'
        report[section]=dict(cases=rows,sources_sha256=hashes,
            scope='Selected architecture RF ledger, differential clock, internal pulse loads, dynamic rail and causal 10-bit SAR. Channel 38, one packet seed, both supply-delay signs, wanted -67 dBm and +2 MHz blocker -50 dBm before assigned 2 dB external loss. CW versus nominal GFSK PRBS15. Converter-generated load is NOT fed back into the package in this diagnostic. No PER, full reference test waveform, negative offsets, TX exchange or physical compliance qualification.')
        if args.feedback:
            report[section]['scope']=report[section]['scope'].replace(
                'Converter-generated load is NOT fed back into the package in this diagnostic.',
                'Converter-generated load is iterated through shared package, reference and differential input response, up to four passes. Convergence is reported per case; this is waveform relaxation around the operating envelope, not live lifecycle co-simulation.')
        write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))
        return
    if args.input_envelope:
        from reference_input_probe import paired_input_envelope
        for ret in (.25e-9,2e-9):
            for esl in (.2e-9,1e-9):
                raw,context=revision_clock_environment(design,'rf',2.4e9,return_l=ret,die_esl=esl)
                raw['internal_switching_loads']=[
                    dict(owner='timing',mean_a=.010,event_hz=150e6,tau_s=.2e-9,harmonics=64),
                    dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
                result=paired_input_envelope(raw,dict(mismatch=.2,opposed=False,cm_gain=-.1))
                rows.append(dict(context,internal_switching_loads=raw['internal_switching_loads'],return_l_h=ret,die_esl_h=esl,result=result))
                print(ret,esl,'observed excursion',any(x['observed_outside_assigned_envelope'] for x in result['legs']),flush=True)
        verify_sources()
        report['package_factorial_input_envelope']=dict(cases=rows,sources_sha256=hashes,
            scope='Fixed-phase 2.4 GHz RF local input waveform only; shared configured differential source amplitude, 20% aligned mismatch, normal internal-current hypothesis. Independent return inductance and die-decoupling ESL corners. No downstream payload or physical assembly qualification.')
        write_report(path,report)
        return
    networks=b.network_cases(design)
    if args.wired or args.rf:networks=[x for x in networks if x[0]!='higher_inductance_probe']
    if args.feed_candidate:networks=[x for x in networks if x[0]=='lower_return_probe']
    modes=[('wire',2.5e9,312.5e6)] if args.wired else [('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)]
    if args.rf:modes=modes[:2]
    for label,return_l,die_esl in networks:
        for mode,carrier,word in modes:
            for sign in ((-1.,) if args.rf else (1.,-1.)):
                raw,context=revision_clock_environment(design,mode,carrier,return_l=return_l,die_esl=die_esl,feed_candidate=args.feed_candidate)
                if args.feed_candidate:
                    raw['internal_switching_loads']=[dict(owner='timing',mean_a=.020,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),dict(owner='core',mean_a=.040,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
                try:
                    e,r=b.reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,supply_sign=sign,sensitivity_ps_per_mv=.0125 if args.lower_sensitivity else None)
                except ValueError as error:
                    if str(error)!='Internal pulse mean exceeds owner DC budget':raise
                    e=None;r=dict(status='load_rejected',reason=str(error))
                row=dict(context,internal_switching_loads=raw.get('internal_switching_loads',[]),network_case=label,return_l_h=return_l,die_esl_h=die_esl,mode=mode,carrier_hz=carrier,supply_sign=sign,clock=r)
                if e is not None:
                    dc=e['ledger']['local_payload_clock_core_rail_v']
                    bound=sum(t['clock_rail_voltage_peak_v'] for t in e['host_spectrum']['tones'])
                    row['rail']=dict(conservative_interval_v=[dc-bound,dc+bound],scope='Finite-tone triangle bound, not observed extrema. Leaving a voltage limit does not establish a physical violation.')
                    if args.wired:
                        from wired_lock_probe import peer_for_environment,resolved_case
                        cases=[]
                        for offset in (0,4,8,12):
                            peer,edges,_=peer_for_environment(e,offset)
                            for phase in (-.35,.35):
                                for ppm in (-100.,100.):
                                    cases.append(dict(launch_offset_ui=offset,result=resolved_case(peer,edges,phase,ppm,4,True)))
                        row['wired']=cases
                        row['continuously_ready_cases']=sum(x['result']['readiness']==1. and x['result']['final_qualified'] for x in cases)
                        row['total_heldout_errors']=sum(x['result']['errors'] for x in cases)
                    if args.rf:
                        from wideband_packet import run_acquisition_case
                        from selected_rf import minimum_envelope_oversample
                        row['rf']=run_acquisition_case(e,431,start_sample=137,carrier_offset_hz=-120e3,
                            transmit=True,oversample=minimum_envelope_oversample(e))
                        print('RF payload',label,carrier,row['rf']['payload_correct'],row['rf']['raw_bit_errors'],flush=True)
                rows.append(row)
                print(label,mode,sign,r['status'],'ready',row.get('continuously_ready_cases'),'errors',row.get('total_heldout_errors'),flush=True)
    scope=('Matched 0.25/0.5 nH downstream wired test: selected 20% aligned input mismatch, both delay signs, four launches and four independent peer phase/ppm corners. Each held-out window is 1200 bits, root-localized detected crossings, unchanged readiness criterion. No long BER, asynchronous internal phase, physical detector precision or protocol lifecycle qualification.' if args.wired else
        '18 selected differential clock/rail cases across three package hypotheses, RF endpoints and wired, both delay signs. Clock acceptance is not wired readiness or RF packet acceptance. Higher-inductance case also changes die ESL.')
    if args.rf:scope='Matched 0.25/0.5 nH blocked RF acquisition at two endpoints, negative supply-delay sign only, seed 431, arrival 137 samples and -120 kHz CFO. Causal SAR/rail/input feedback with independent legacy-training acquisition and coded DATA. Fixed gain, diagnostic HE20 DATA not a standards-valid HE packet; no AGC, PER or full lifecycle qualification.'
    scope+=(' Candidate 1 ohm feed, 0.25 nH return, twice internal pulses within unchanged DC budgets;' if args.feed_candidate else ' Default full internal pulse hypothesis;')
    scope+=f' 1 V differential source, {0.0125 if args.lower_sensitivity else 0.025} ps/mV and 500 pF; measured silicon/assembly performance is not established.'
    verify_sources()
    section='package_rf_screen' if args.rf else 'package_wired_screen' if args.wired else 'package_clock_screen'
    if args.lower_sensitivity:section+='_lower_sensitivity'
    report[section]=dict(cases=rows,scope=scope,sources_sha256=hashes)
    write_report(path,json.loads(json.dumps(report,default=lambda x:x.item())))


if __name__=='__main__':
    main()
