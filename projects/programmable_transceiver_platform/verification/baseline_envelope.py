"""Selected first-chip baseline under the shared electrical environment.

Fast entry point for architecture decisions. Imports the existing shared
network/timing model; does not relabel its legacy payload fixtures as baseline
qualification. Report fields explicitly identify migration work still missing.
"""
import hashlib
from copy import deepcopy
import json
import math
from dataclasses import replace
from pathlib import Path

import numpy as np

from robustness_envelope import P, operating_environment, shared_board_candidate, write_evidence
from wired_envelope import causal_receiver_envelope, physical_receiver
from selected_rf import wideband_receive, wideband_transmit, driver_wake_response, minimum_envelope_oversample, reference_supply_transfer, reference_supply_parameters, clock_supply_delay_pole, clock_supply_sensitivity, reference_acceptance_parameters
from ble_packet import joined_scan_request, transmitted_scan_response
from converter_dynamics import SARParameters, load_response, response_change, tone_precision, supply_delay_gain, reference_load_parameters
from design_definition import load_design


MODE_CURRENT_A = {
    'rf': dict(core=.040, host=.110, timing=.044, rf=.044, wire=.002),
    'wire': dict(core=.040, host=.110, timing=.044, rf=.002, wire=.096),
}


# One package catalog for every joined bench. Labels are evidence identities,
# not claims that a compatible assembly has achieved these parasitics.
def network_cases(design=None):
    design=load_design() if design is None else design
    power=design.architecture['blocks']['power']['parameters']
    return (('selected',.5e-9,200e-12),
            ('lower_return_probe',power['shared_return_l_h'],power['reduced_pdn_model']['network']['die_esl']),
            ('higher_inductance_probe',2e-9,1e-9))


BASELINE_PACKAGE_CASE='lower_return_probe'
# 'selected' is the retained original 0.5 nH evidence identity, not the current target.



def selected_dc_ledger(mode, candidate, *, source_v=3.3, h2d_internal_a=.0240625, wire_current_a=None, owner_current_a=None):
    """Charge H2D internal current once, within HOST, at the local load node.

    Unspent HOST allocation is a constant feed-node burden. Its switching
    spectrum is unknown, not silently represented by a duplicate clock load.
    All timing static and switching power is already inside the 44 mA budget.
    """
    budget=dict(MODE_CURRENT_A[mode] if owner_current_a is None else owner_current_a)
    if set(budget)!=set(MODE_CURRENT_A[mode]) or not all(math.isfinite(v) and v>=0 for v in budget.values()):
        raise ValueError('Complete finite nonnegative current ownership required')
    if wire_current_a is not None:
        if mode!='wire' or not math.isfinite(wire_current_a) or not .002<=wire_current_a<=.096:
            raise ValueError('Wired allocation must remain within the existing 2–96 mA envelope')
        budget['wire']=wire_current_a
    if not math.isfinite(source_v) or source_v<=0 or not 0<=h2d_internal_a<=budget['host']:
        raise ValueError('Positive source and H2D current within HOST allowance required')
    total=sum(budget.values())
    host=budget['host']-h2d_internal_a
    local=total-host
    n=candidate['network'];rf=n['feed_r'];rp=n['package_r'];rg=candidate['return_r_ohm']
    board=source_v-rf*total;ground=rg*total
    rail=board-rp*local-ground;host_rail=board-ground
    loss=rf*total**2+rp*local**2+rg*total**2
    delivered=rail*local+host_rail*host
    return dict(owner_current_a=dict(budget),total_chip_supply_current_a=total,
        host_node_current_a=host,local_branch_current_a=local,
        h2d_internal_current_within_host_a=h2d_internal_a,
        board_supply_v=board,die_return_v=ground,local_payload_clock_core_rail_v=rail,
        rf_clock_core_rail_v=rail,host_rail_v=host_rail,source_v=source_v,
        source_power_w=source_v*total,delivered_electrical_power_w=delivered,
        resistive_loss_w=loss,power_balance_residual_w=source_v*total-delivered-loss,
        physical_pin_current_qualification=False)


def rail_excursion(tones, *, dc_v, samples_per_fastest_period=16):
    """Coherent periodic trace plus a derivative-bounded grid enclosure."""
    frequencies=[round(t['frequency_hz']) for t in tones]
    if any(abs(f-t['frequency_hz'])>1e-6 for f,t in zip(frequencies,tones)):
        raise ValueError('This periodic screen requires integer-Hz harmonics')
    fundamental=math.gcd(*frequencies)
    count=2**math.ceil(math.log2(samples_per_fastest_period*max(frequencies)/fundamental))
    requested_count=count
    # A coarser grid is still rigorously enclosed by the derivative bound.
    # Cap runtime without silently claiming the requested temporal resolution.
    count=min(count,2**20)
    dt=1/(count*fundamental);times=np.arange(count)*dt
    ripple=sum(t['clock_rail_voltage_peak_v']*np.cos(2*math.pi*t['frequency_hz']*times+t['voltage_phase_rad']) for t in tones)
    error=sum(2*math.pi*t['frequency_hz']*t['clock_rail_voltage_peak_v'] for t in tones)*dt/2
    lower=dc_v+float(min(ripple));upper=dc_v+float(max(ripple))
    return dict(sampled_interval_v=[lower,upper],enclosed_interval_v=[lower-error,upper+error],
        grid_enclosure_error_v=error,samples=count,requested_samples=requested_count,
        grid_capped=count<requested_count,period_s=1/fundamental,
        observed_below_legacy_2p5v_floor=lower<2.5,
        guaranteed_inside_legacy_2p5_to_3p6v_fixture=lower-error>=2.5 and upper+error<=3.6,
        scope='Exact finite-tone waveform at sampled times with a conservative derivative enclosure between samples; omitted physical currents/noise are not covered. The legacy fixture interval is not a silicon specification.')


def _electrical_environment_seed(contract, mode, carrier, word, *, return_l, die_esl, external_input=None, output_cap_f=10e-12, network_candidate=None,h2d_word_hz=312.5e6,h2d_internal_charge_c=7e-12,d2h_internal_charge_c=7e-12,reference_fraction_per_v=.1,reference_pole_hz=10e6,output_voltage_v=3.3):
    """Electrical seed; use reference_payload_environment for the selected delivered clock.

    Direct consumers are retained pre-migration diagnostic controls, not a
    differential input model. USB static screens intentionally omit REF loading.
    """
    if network_candidate is None:
        candidate=shared_board_candidate()
        candidate['network'].update(die_c=500e-12,die_esr=.5)
    else:
        candidate=dict(network_candidate,network=dict(network_candidate['network']))
    candidate['return_l_h']=return_l
    candidate['network']['die_esl']=die_esl
    e=operating_environment(contract,candidate,carrier_hz=carrier,d2h_word_hz=word,h2d_word_hz=h2d_word_hz,
        payload_engine=mode,payload_current_a=MODE_CURRENT_A[mode][mode],
        h2d_internal_charge_c=h2d_internal_charge_c,d2h_internal_charge_c=d2h_internal_charge_c,d2h_harmonics=12,output_cap_f=output_cap_f,output_voltage_v=output_voltage_v,
        reference_fraction_per_v=reference_fraction_per_v,reference_pole_hz=reference_pole_hz,
        external_input=dict(dict(receiver_noise_v=75e-6,downstream_stage_rms_s=15e-15),**(external_input or {})))
    # AC network is linear and independent of DC. Replace the legacy ledger
    # before any rail/headroom consumer, including real packet campaigns.
    e['ledger']=selected_dc_ledger(mode,candidate)
    e['design_parameter_source']='legacy_fixed_current_and_load_seed_not_inventory'
    e['clock_input_configuration']=dict(contract['physical_services']['external_clock_input'])
    e['control_hz']=e['host_spectrum']['h2d_word_hz']/8
    e['control_clock_owner']='FPGA H2D physical DDR clock divided by four; SPI/reset recovery is separate'
    return e


def design_for_contract(contract,design=None):
    """Resolve once or preserve an explicitly supplied immutable snapshot."""
    from design_definition import DesignDefinition
    if design is None:
        current=load_design()
        if contract!=current.contract:
            raise ValueError('Contract differs from current design; supply an explicit design snapshot')
        return current
    if not isinstance(design,DesignDefinition) or design.contract!=contract:
        raise ValueError('Contract does not match supplied design snapshot')
    return design


def inventory_environment(contract,architecture,mode,carrier,word,*,inventory_mode=None,design=None,diagnostic_input_reason=None,**options):
    """Current-inventory seed for common-envelope benches; historical seeds remain controls.

    The five-port network lumps converter current at its local core load node.
    This is a declared network reduction, not a claim that CONV is on DVDD.
    Source/package constants remain shared across RF and wired selections.
    """
    from rf_quality_budget import current_allocation
    from design_definition import DesignDefinition
    snapshot=DesignDefinition.from_documents(contract,architecture)
    if design is None:
        design=snapshot
    elif not isinstance(design,DesignDefinition) or design.fingerprint!=snapshot.fingerprint:
        raise ValueError('Supplied design does not match inventory documents')
    contract,architecture=design.contract,design.architecture
    selected_mode=inventory_mode or ('rf_rx' if mode=='rf' else 'wired')
    if (mode,selected_mode) not in (('rf','rf_rx'),('rf','rf_tx'),('wire','wired'),('wire','usb')):
        raise ValueError('Inventory mode incompatible with payload engine')
    report=current_allocation(architecture,selected_mode,
                              branch='external_rf_clock' if mode=='rf' else None)
    rail=report['by_rail_ma']
    budget=dict(core=(rail.get('core',0)+rail.get('conv',0))/1000,
                host=rail.get('host',0)/1000,timing=rail.get('pll',0)/1000,
                rf=rail.get('rf',0)/1000,wire=rail.get('wire',0)/1000)
    if not math.isclose(sum(budget.values()),report['total_ma']/1000,abs_tol=1e-12):
        raise ValueError('Inventory current lost in network reduction')
    power=architecture['blocks']['power']['parameters']
    reduced=power['reduced_pdn_model']
    candidate=dict(name='lower_feed_resistance',return_r_ohm=reduced['return_r_ohm'],
        network=dict(reduced['network'],package_l=power['bond_l_h']))
    if 'network_candidate' in options:
        raise ValueError('Change the shared design or declare a physical scenario instead of replacing its network')
    options['network_candidate']=candidate
    for key in ('h2d_internal_charge_c','d2h_internal_charge_c'):
        owned=architecture['model_assumptions']['host_switching']['parameters'][key]
        if key in options and options[key]!=owned:
            raise ValueError('Host transition charge conflicts with design snapshot: '+key)
        options[key]=owned
    acceptance=architecture['model_assumptions']['reference_input_acceptance']['parameters']
    input_parameters=dict(receiver_noise_v=architecture['blocks']['refinput']['parameters']['receiver_noise_v'],
        downstream_stage_rms_s=architecture['blocks']['clocktree']['parameters']['downstream_stage_rms_s'],
        threshold_v=acceptance['threshold_v'],peak_limit_v=acceptance['effective_peak_limit_v'])
    input_overrides=options.get('external_input') or {}
    changed={key:value for key,value in input_overrides.items() if key not in input_parameters or value!=input_parameters[key]}
    if changed and (not isinstance(diagnostic_input_reason,str) or not diagnostic_input_reason.strip()):
        raise ValueError('Clock-input changes require a reasoned diagnostic intervention or a changed design snapshot')
    input_parameters.update(input_overrides)
    options['external_input']=input_parameters
    options.setdefault('die_esl',reduced['network']['die_esl'])
    options.setdefault('return_l',power['shared_return_l_h'])
    options.setdefault('output_cap_f',contract['physical_services']['host_output']['full_rate_external_load_target_f'])
    voltage=contract['physical_services']['host_output']['voltage_v']
    if 'output_voltage_v' in options and options['output_voltage_v']!=voltage:
        raise ValueError('Output voltage conflicts with shared contract')
    options['output_voltage_v']=voltage
    reference_parameters={key:architecture['blocks']['refbuf']['parameters'][key]
        for key in ('target_v','supply_fraction_per_v','supply_pole_hz')}
    for option,key in (('reference_fraction_per_v','supply_fraction_per_v'),('reference_pole_hz','supply_pole_hz')):
        if option in options and options[option]!=reference_parameters[key]:
            raise ValueError('Reference supply coupling conflicts with shared design')
        options[option]=reference_parameters[key]
    profile=contract['transport']['profiles']['ddr156']
    options.setdefault('h2d_word_hz',profile['clock_hz']*profile['edges'])
    e=_electrical_environment_seed(contract,mode,carrier,word,**options)
    e['reference_supply_parameters']=reference_parameters
    e['reference_pad_parameters']=dict(architecture['blocks']['refpad']['parameters'])
    e['reference_package_parameters']=dict(architecture['model_assumptions']['reference_input_package']['parameters'])
    if changed:
        e['diagnostic_input_intervention']=dict(changed)
        e['diagnostic_input_reason']=diagnostic_input_reason
    from dataclasses import asdict
    from converter_dynamics import parameters_from_inventory
    e['converter_parameters']=asdict(parameters_from_inventory(architecture))
    e['comparator_parameters']=dict(architecture['model_assumptions']['paired_sar_comparator']['parameters'])
    from protocol_pad import SharedWiredPad
    e['wired_pad_capacitance_f']=SharedWiredPad.from_architecture(architecture).C.tolist()
    e['rf_receive_supply_parameters']=dict(architecture['model_assumptions']['rf_receive_supply']['parameters'])
    e['wired_supply_gain_parameters']=dict(architecture['model_assumptions']['wired_supply_gain']['parameters'])
    e['wired_usb_parameters']=dict(architecture['blocks']['usbhs']['parameters'])
    e['wired_usbfs_parameters']=dict(architecture['blocks']['usbfs']['parameters'])
    e['wired_ctle_parameters']=dict(architecture['blocks']['ctle']['parameters'])
    e['wired_cdr_parameters']=dict(architecture['blocks']['cdr']['parameters'])
    e['wired_tracking_sampler_count']=architecture['blocks']['slicer']['parameters'].get('tracking_sampler_count',3)
    e['control_hz']=e['host_spectrum']['h2d_word_hz']/contract['transport']['profiles']['ddr156']['edges']/architecture['control_semantics']['scheduler_clock_divider']
    e['control_clock_owner']='H2D physical clock / control_semantics.scheduler_clock_divider'
    e['transport_parameters']=dict(startup_s=contract['physical_services']['sar_timing']['startup']['assigned_guard_s'],
        h2d_word_hz=e['host_spectrum']['h2d_word_hz'],d2h_word_hz=e['host_spectrum']['d2h_word_hz'],
        legacy_tx_queue_bits=contract['transport']['scheduling']['egress_bits_per_source'],
        control_hz=e['control_hz'],queue_status=contract['transport']['scheduling']['fifo_budget_status'])
    e['reference_acceptance_parameters']=dict(acceptance)
    e['clock_input_noise_parameters']={key:input_parameters[key] for key in
        ('receiver_noise_v','downstream_stage_rms_s')}
    e['adc_noise_parameters']=dict(architecture['model_assumptions']['paired_adc']['parameters'])
    e['dac_noise_parameters']=dict(architecture['model_assumptions']['paired_dac']['parameters'])
    e['rf_output_parameters']=dict(architecture['model_assumptions']['rf_output']['parameters'])
    e['cdr_supply_delay_parameters']={key:architecture['blocks']['cdr']['parameters'][key]
        for key in ('supply_sensitivity_ps_per_mv','delay_pole_hz')}
    e['fpga_tx_preparation']=dict(architecture['rf_interoperability'].get('fpga_tx_preparation',{}))
    e['filter_parameters']={name:architecture['blocks'][name]['parameters']
        for name in ('rxfilter_i','rxfilter_q','txfilter_i','txfilter_q')}
    e['transmitter_parameters']={name:architecture['blocks'][name]['parameters'] for name in ('dac_i','dac_q','rfdriver')}
    e['receiver_parameters']={name:architecture['blocks'][name]['parameters']
                              for name in ('pga_i','pga_q','lna','adc_i','adc_q')}
    e['design_parameter_source']='architecture_inventory_with_explicit_case_overrides'
    e['design_provenance']=design.provenance()
    e['inventory_current_a']=budget
    e['inventory_current_report']=report
    board=architecture['blocks']['board']['parameters']
    source_v=board['analog_supply_v']
    if source_v!=board['digital_supply_v']:
        raise ValueError('Reduced common-feed model requires equal analog and digital board supplies')
    e['board_source_v']=source_v
    e['ledger']=selected_dc_ledger(mode,e['network'],source_v=source_v,owner_current_a=budget,
        h2d_internal_a=e['host_spectrum']['chip_h2d_internal_mean_a'])
    e['payload_current_a']=budget[mode]
    return e


def configured_environment(config, scenario=None):
    """Build the inventory electrical seed from one resolved design/configuration.

    This does not qualify delivered clocks or decode packets. The provenance
    travels with the environment into downstream compositions.
    """
    from design_definition import ResolvedConfiguration, Scenario
    if not isinstance(config, ResolvedConfiguration):
        raise TypeError('Resolved shared-design configuration required')
    if scenario is None:
        scenario=Scenario()
    if not isinstance(scenario, Scenario):
        raise TypeError('Explicit Scenario required')
    design=config.design
    scenario.operating_conditions(design)  # Validate before constructing the electrical seed.
    electrical_options=scenario.electrical_options(design)
    electrical_options['h2d_word_hz']=config.h2d_word_hz
    environment=inventory_environment(design.contract,design.architecture,
        config.engine,config.reference_hz,config.host_word_hz,
        inventory_mode=config.inventory_mode,design=design,**electrical_options)
    return _bind_configured_environment(config,scenario,environment)


def configured_forwarded_clock(config,scenario=None,**initial_conditions):
    """Join the shared paired input/package to a retained reference-sampled PLL."""
    from reference_input_probe import ConfiguredReferenceEdges
    from video_alignment import ConfiguredLaneClock
    if config.clock_source!='forwarded_word' or config.engine!='wire':
        raise ValueError('Forwarded wired configuration required')
    e=configured_environment(config,scenario)
    if 'internal_switching_loads' not in e:
        e['internal_switching_loads']=[
            dict(owner='timing',mean_a=.010,event_hz=config.wire_clock_hz/16,tau_s=.2e-9,harmonics=64),
            dict(owner='core',mean_a=.020,event_hz=config.h2d_clock_hz,tau_s=.2e-9,harmonics=64)]
    edges=ConfiguredReferenceEdges(e,source_peak_v=None if scenario is None else scenario.reference_peak_v)
    clock=ConfiguredLaneClock(config,reference_edge_provider=edges,**initial_conditions)
    clock.reference_input=edges
    return clock


def _bind_configured_environment(config,scenario,environment):
    """Apply the same conditions and transport binding to ordinary and diagnostic seeds."""
    conditions=scenario.operating_conditions(config.design)
    environment['converter_parameters']['temperature_k']=conditions['temperature_k']
    environment['operating_conditions']=conditions
    environment['clock_domains']=config.clock_domains
    environment['scenario_assumptions']=dict(scenario.assumptions)
    environment['transport_parameters']['d2h_word_hz']=config.host_word_hz
    environment['transport_parameters']['h2d_word_hz']=config.h2d_word_hz
    environment['control_hz']=config.control_hz
    environment['transport_parameters']['control_hz']=config.control_hz
    cdr=environment['wired_cdr_parameters']
    if config.cdr_periodic_tracking:
        if cdr.get('detector_model')!='phase_bank':
            raise ValueError('Periodic tracking requires a phase-bank detector')
        budget=config.design.architecture['direct_stream_service']['budget']
        # Reserve two frames for arbitration/framing; keep the ordinary framed
        # host clocks and epoch throughout acquisition and payload operation.
        cdr['periodic_observation_link']=dict(word_hz=config.host_word_hz,word_bits=10,
            latency_s=(128+budget['rx_cdc_host_cycles']+budget['fpga_capture_cycles'])/config.host_word_hz+budget['board_margin_s'],
            queue_bits=config.design.architecture['resource_policy']['memory_bits']['egress'],epoch=0,
            coefficient_return_s=(128+52)/config.h2d_word_hz+budget['tx_cdc_cycles']/budget['tx_fifo_read_hz'])
    else:
        cdr['periodic_clock_compute_delay_s']=None
        cdr['periodic_observation_link']=None
        cdr['acquisition_timeout_ui']=cdr.get('ordinary_acquisition_timeout_ui',1024)
    environment['resolved_configuration']=config.record()
    environment['scenario_overrides']=scenario.record()
    return environment


class ConfiguredReceiveModel:
    """Shared-design adapter for the existing coded wideband diagnostic chain.

    Fixed known training and ideal packet boundaries; this is not an HE PPDU
    or a universal protocol receiver. Independent FPGA decoding stays outside
    the analog model and is exercised by wideband_packet.
    """
    def __init__(self,config,scenario):
        from design_definition import ResolvedConfiguration,Scenario
        if not isinstance(config,ResolvedConfiguration):
            raise TypeError('Resolved shared-design configuration required')
        if not isinstance(scenario,Scenario):
            raise TypeError('Scenario required')
        if config.engine!='rf' or config.direction!='rx':
            raise ValueError('This packet adapter currently supports RF receive only')
        if scenario.wanted_dbm is None or scenario.reference_peak_v is None:
            raise ValueError('Wanted level and external reference drive must be explicit')
        self._config=config
        self._scenario=scenario
        self._seed=configured_environment(config,scenario)
        self._environment,self._clock=reference_payload_environment(self._seed,
            dict(link_r_ohm=1e-5),False,source_peak_v=scenario.reference_peak_v)

    @property
    def config(self):
        return self._config

    @property
    def scenario(self):
        return self._scenario

    @property
    def seed(self):
        return deepcopy(self._seed)

    @property
    def environment(self):
        return deepcopy(self._environment)

    @property
    def clock(self):
        return deepcopy(self._clock)

    def receive(self,packet):
        from wideband_packet import run_case,coded_data_geometry
        if not isinstance(packet,bytes):
            raise TypeError('Diagnostic packet payload must be bytes')
        coded_data_geometry(len(packet))
        record=dict(design_provenance=self._config.design.provenance(),
                    resolved_configuration=self._config.record(),
                    scenario_overrides=self._scenario.record(),
                    scenario_assumptions=dict(self._scenario.assumptions),
                    operating_conditions=deepcopy(self._seed['operating_conditions']),
                    stimuli=self._scenario.stimulus_record(),clock=deepcopy(self._clock))
        if self._environment is None:
            return dict(record,status='clock_rejected',result=None)
        result=run_case(self._environment,0,payload_bytes=len(packet),packet=packet,
                        wanted_dbm=self._scenario.wanted_dbm,blocker_dbm=self._scenario.blocker_dbm)
        return dict(record,status='evaluated',result=result)


def build_model(config,scenario):
    """Build the supported packet adapter; unsupported engines fail explicitly."""
    return ConfiguredReceiveModel(config,scenario)


def selected_environment(contract,mode,carrier,word,*,design=None,**options):
    """Convenience entry point for the current architecture inventory.

    Explicit package/load overrides remain valid adverse or simplified tests.
    This creates an electrical seed, not delivered-clock qualification: compose
    reference_payload_environment when a bench claims selected clock behavior.
    """
    from design_definition import load_design
    design=design_for_contract(contract,design)
    return inventory_environment(contract,design.architecture,mode,carrier,word,design=design,**options)


def environment_converter_parameters(environment):
    """Inventory simulations cannot silently fall back to the bare SAR fixture."""
    if 'converter_parameters' in environment:
        parameters=environment['converter_parameters']
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            from dataclasses import fields
            if not isinstance(parameters,dict) or set(parameters)!={field.name for field in fields(SARParameters)}:
                raise ValueError('Inventory environment requires complete converter parameters')
        return SARParameters(**parameters)
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        raise ValueError('Inventory environment missing selected converter parameters')
    return SARParameters()  # Explicit legacy/primitive environment only.


def receiver_inventory_options(environment,architecture=None):
    """ADC and legal PGA/LNA requirements for integrated narrowband benches.

    Waveform, filter setting, sample divider and explicit stress overrides are
    the caller's responsibility. This does not establish their feasibility.
    """
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        if 'receiver_parameters' not in environment:
            raise ValueError('Inventory environment missing selected receiver parameters')
        if architecture is not None and any(
                architecture['blocks'][name]['parameters']!=values
                for name,values in environment['receiver_parameters'].items()):
            raise ValueError('Receiver architecture differs from environment snapshot')
    if architecture is None and 'receiver_parameters' in environment:
        blocks={name:dict(parameters=values) for name,values in environment['receiver_parameters'].items()}
    else:
        if architecture is None:
            raise ValueError('Receiver inventory requires environment parameters or an explicit architecture')
        blocks=architecture['blocks']
    if architecture is not None:
        from converter_dynamics import parameters_from_inventory
        converter=parameters_from_inventory(architecture)
        if 'operating_conditions' in environment:
            converter=replace(converter,temperature_k=environment['operating_conditions']['temperature_c']+273.15)
        if 'converter_parameters' in environment and environment_converter_parameters(environment)!=converter:
            raise ValueError('Converter architecture differs from environment snapshot')
    else:
        if 'converter_parameters' not in environment:
            raise ValueError('Receiver inventory requires converter parameters')
        converter=environment_converter_parameters(environment)
    codes=tuple(blocks['pga_i']['parameters']['gain_db'])
    if codes!=tuple(blocks['pga_q']['parameters']['gain_db']):
        raise ValueError('Paired receiver requires the same I/Q gain codes')
    config=environment.get('resolved_configuration')
    initial_gain=min(codes,key=lambda value:abs(value-39.)) if config is None else config['pga_gain_db']
    if initial_gain not in codes:
        raise ValueError('Receiver initial gain conflicts with inventory')
    return dict(noise_figure_db=blocks['lna']['parameters']['noise_figure_db'],
        input_iip3_dbm=blocks['lna']['parameters']['iip3_dbm'],
        converter_bits=blocks['adc_i']['parameters']['native_bits'],
        initial_gain_db=initial_gain,
        maximum_gain_db=max(codes),gain_codes_db=codes,
        sar_parameters=converter)


def reference_feedback_response(trace,environment,**options):
    """Use the selected fixed recharge allocation, input topology and delay law."""
    # Recharge replaces its fixed planning reserve, as in selected_lifecycle;
    # a packet-dependent mean must not define a different DC operating point.
    options.setdefault('dc_reference_a',trace['reference_limit_a'])
    bound=any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration'))
    required=['local_supply_delay_sign','local_supply_sensitivity_ps_per_mv']
    if 'periodic_clock' in environment:required.append('reference_load_parameters')
    if bound:
        missing=[key for key in required if key not in environment]
        if missing:raise ValueError('Design-bound feedback missing parameters: '+', '.join(missing))
    return load_response(trace,environment['network'],
        reference_input=reference_load_parameters(environment) if 'periodic_clock' in environment else None,
        supply_sign=environment.get('local_supply_delay_sign',1.),
        sensitivity_ps_per_mv=clock_supply_sensitivity(environment),
        reference_supply_parameters=reference_supply_parameters(environment),
        delay_pole_hz=clock_supply_delay_pole(environment),**options)


def coupled_scan_request(environment,contract,*,rx_options,stimulus,progress=None):
    """Iterate causal SAR load through the shared rail/input response."""
    supplied_options=dict(rx_options)
    inventory=receiver_inventory_options(environment)
    rx_options=dict(inventory,**rx_options)
    config=environment.get('resolved_configuration')
    if config is not None:
        if config['engine']!='rf' or config['direction']!='rx':
            raise ValueError('RF receive configuration required')
        for key in ('noise_figure_db','input_iip3_dbm','converter_bits','sar_parameters','gain_codes_db','maximum_gain_db'):
            if key in stimulus or rx_options[key]!=inventory[key]:
                raise ValueError('Packet assumptions conflict with shared design: '+key)
        for key,value in (('lo_divider',config['sample_divider']),('initial_gain_db',config['pga_gain_db'])):
            if key in stimulus or (key in supplied_options and supplied_options[key]!=value):
                raise ValueError('Packet controls conflict with resolved configuration: '+key)
            rx_options[key]=value
    response=None;iterations=[]
    for iteration in range(4):
        current=environment if response is None else dict(environment,local_load_response=response)
        capture={}
        received=joined_scan_request(current,contract,**rx_options,**stimulus,load_capture=capture)
        coupled='periodic_clock' in environment
        updated,load=reference_feedback_response(capture,environment)
        rms,peak,converged=response_change(updated,response)
        input_change=None
        if response is not None and coupled:
            mask=(updated['times_s']>=response['times_s'][0])&(updated['times_s']<=response['times_s'][-1])
            input_change=float(max(abs(updated['input_v'][mask]-np.interp(updated['times_s'][mask],response['times_s'],response['input_v']))))
        converged=converged and (not coupled or (input_change is not None and input_change<=1e-6))
        iterations.append(dict(iteration=iteration,load_response=load,
            input_voltage_peak_change_v=input_change,
            rail_rms_change_v=rms,rail_maximum_change_v=peak,
            correct_request=received['correct_request']))
        if progress is not None:progress(iterations[-1])
        response=updated
        if converged:break
    received['reference_feedback']=dict(iterations=iterations,numerical_feedback_converged=converged)
    received.update({key:deepcopy(environment[key]) for key in ('design_provenance','resolved_configuration',
        'scenario_overrides','scenario_assumptions','operating_conditions') if key in environment})
    return received,current


def coupled_scan_reply(request,environment,contract,*,tx_options,modulation_a=.007,grid_s=1e-9,guard_s=2e-6,initial_response=None,capture_out=None):
    """Sensitivity: signal-correlated reduction of already reserved warm bias."""
    from converter_dynamics import sampled_load_response,sum_load_responses,feedback_change
    from ble_packet import packet_driver_bias
    driver_bias=packet_driver_bias(environment)
    if not 0<=modulation_a<=driver_bias:raise ValueError('TX modulation must fit existing driver reservation')
    original=environment.get('local_load_response');response=initial_response;iterations=[]
    for iteration in range(4):
        current=environment if response is None else dict(environment,local_load_response=sum_load_responses(original,response))
        capture={};transmitted=transmitted_scan_response(request,current,contract,**tx_options,load_capture=capture)
        if not transmitted.get('transmitted',False):return transmitted,current
        # Fixed 1.2 V open-circuit envelope normalization: no fitted burst peak
        # or future samples enter the current law. Warm mute consumes the shared driver allocation;
        # output activity releases at most modulation_a of that reservation.
        delta=-modulation_a*capture['normalized_output_power']
        updated,report=sampled_load_response(capture['times_s'],delta,environment,grid_s=grid_s,guard_s=guard_s)
        rms,peak,_=response_change(updated,response)
        agreement=feedback_change(updated,response);converged=agreement['converged']
        iterations.append(dict(iteration=iteration,load_response=report,feedback_agreement=agreement,rail_rms_change_v=rms,
            rail_peak_change_v=peak,peer_correct_response=transmitted.get('peer_correct_response',False)))
        response=updated
        if converged:break
    if capture_out is not None:capture_out.update(response=response)
    transmitted['tx_current_feedback']=dict(iterations=iterations,numerical_feedback_converged=converged,
        modulation_a=modulation_a,minimum_driver_current_a=driver_bias-modulation_a,driver_bias_current_a=driver_bias,
        scope='Assigned warm-current release proportional to instantaneous normalized open-envelope power, fixed 1.2 V scale clipped at unity; release bounded by the shared driver allocation. Not inferred driver current, positive extra load, RF-cycle switching, bias wake, RX rerun or full lifecycle. Guarded waveform relaxation retains original RX load response and absolute timing.')
    return transmitted,current


def narrowband_exchange(contract,*,source_peak_v=1.,include_swing_controls=True,design=None):
    from design_definition import DesignDefinition,Scenario
    design=design_for_contract(contract,design)
    codes=design.architecture['blocks']['pga_i']['parameters']['gain_db']
    config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
        sample_divider=256,pga_gain_db=min(codes,key=lambda gain:abs(gain-39.)))
    tx_config=design.configure(engine='rf',direction='tx',reference_hz=config.reference_hz,sample_divider=256)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario(reference_peak_v=source_peak_v).override(
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl,
            reason='Package uncertainty case: '+label)
        e=configured_environment(config,scenario)
        previous_environment=e
        e,clock_report=reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=source_peak_v)
        if e is None:
            rows.append(dict(network_case=label,clock=clock_report,status='clock_rejected',calibration=None,cases=[],
                resolved_configuration=config.record(),scenario_overrides=scenario.record()))
            continue
        tx_seed=configured_environment(tx_config,scenario)
        tx_environment,tx_clock=reference_payload_environment(tx_seed,dict(link_r_ohm=1e-5),False,source_peak_v=source_peak_v)
        if tx_environment is None:
            rows.append(dict(network_case=label,clock=clock_report,transmit_clock=tx_clock,
                status='transmit_clock_rejected',calibration=None,cases=[],
                design_provenance=design.provenance(),resolved_configuration=config.record(),
                transmit_configuration=tx_config.record(),scenario_overrides=scenario.record()))
            continue
        report_environment={k:v for k,v in e.items() if k not in ('periodic_clock','reference_threshold')}
        rx_options=dict(rx_cutoff_hz=.5e6,
            blocker_offsets_hz=(2e6,4e6),
            aperture_rms_s=10e-12,dynamic_rail=True,
            sar_parameters=environment_converter_parameters(e),mixer_substeps=max(256,minimum_envelope_oversample(e,sample_hz=e['carrier_hz']/256,guard_hz=4.1e6)))
        tx_options=dict(reconstruction_order=None,
            dynamic_rail=True,rf_bias_a=tx_environment['ledger']['owner_current_a']['rf'],mixer_substeps=max(256,minimum_envelope_oversample(tx_environment,sample_hz=e['carrier_hz']/256,guard_hz=4.1e6)))
        def receive(environment=e,**stimulus):
            return coupled_scan_request(environment,contract,rx_options=rx_options,stimulus=stimulus)
        # Separate strong training capture with a known external source time.
        # No scored packet's source end, bits or error is used to retune this.
        training,training_environment=receive(seed=17,wanted_dbm=-60.,blocker_dbm=None)
        training_tx=transmitted_scan_response(training,tx_environment,contract,**tx_options)
        if not training['correct_request'] or not training_tx.get('peer_correct_response',False):
            rows.append(dict(network_case=label,environment=report_environment,clock=clock_report,transmit_clock=tx_clock,
                transmit_configuration=tx_config.record(),
                status='calibration_failed',calibration=dict(training_received=training,training_transmitted=training_tx),cases=[]))
            continue
        rx_correction=training['response']['estimated_request_end_s']-training['source_packet_end_s']
        tx_advance=(training_tx['rf_half_amplitude_start_s']-training_tx['first_dac_consumption_s']+
                    .5/training['settings']['sample_hz']+.5/e['control_hz'])
        calibration=dict(training_seed=17,training_wanted_dbm=-60.,training_blocker_dbm=None,
            rx_timestamp_correction_s=rx_correction,tx_launch_advance_s=tx_advance,
            training_received=training,training_transmitted=training_tx,
            scope='Independent strong known-arrival training capture plus half-cycle DAC/timestamp scheduling allowances. Same two constants applied to every held-out packet at this carrier/filter/package setting. A diagnostic model calibration, not a proven manufacturing procedure or standard air-boundary definition.')
        cases=[]
        for seed in (317,401,509,613,719,827):
            received,current=receive(seed=seed,wanted_dbm=-80.,blocker_dbm=-30.)
            transmitted=transmitted_scan_response(received,tx_environment,contract,**tx_options)
            calibrated=transmitted_scan_response(received,tx_environment,contract,**tx_options,
                rx_timestamp_correction_s=rx_correction,tx_launch_advance_s=tx_advance)
            cases.append(dict(received=received,transmitted=transmitted,calibrated_transmission=calibrated))
        controls=[]
        if label==BASELINE_PACKAGE_CASE and source_peak_v==.5:
            for name,control_environment,blocker in (
                ('previous_environment_same_grid',previous_environment,-30.),
                ('corrected_without_blocker',e,None)):
                control,_=receive(environment=control_environment,seed=719,wanted_dbm=-80.,blocker_dbm=blocker)
                controls.append(dict(name=name,received=control,scope='Paired seed-719 diagnostic at the same 1024-substep grid; not an alternative qualification result.'))
        rows.append(dict(network_case=label,environment=report_environment,clock=clock_report,transmit_clock=tx_clock,
                transmit_configuration=tx_config.record(),status='packet_cases_exercised',
            calibration=calibration,cases=cases,paired_controls=controls))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,source_peak_v=source_peak_v,
        source_swing_control_scope='Same package catalog, receiver and reply chain, with independent calibration at 0.75 V external Thevenin peak; does not replace the 0.5 V baseline. Previous-environment attribution controls are baseline-only.',
        source_swing_controls=[narrowband_exchange(contract,source_peak_v=.75,include_swing_controls=False,design=design)]
            if include_swing_controls else [],
        scope='Actual LE 1M request/reply with causal paired SAR state, code-driven delayed AGC, 18 ns conversion latency and each capture\'s own reference-current feedback. Selected fifth-order all-pole narrow RX and third-order TX. Current architecture allocation, corrected coupled REF_IN events and uninterrupted source phase; recharge-induced input voltage and supply delay perturb actual roots. TX uses a separately settled TX inventory and corrected clock from the same design/package, preserving absolute source time. RX recharge state is not carried into TX; continuous power-domain switching and load-tail handoff remain unmodeled, so this is not a full analog turnaround qualification. Clock rejection and failed independent calibration stop dependent cases explicitly. Same-grid old-environment and blocker-removal controls retain the current-package seed-719 failure. Both uncorrected timing and independent fixed calibration are retained. RF threshold remains diagnostic; six held-out seeds per package are not a PER estimate.')


def converter_design_cases(design):
    """Explicit circuit hypotheses for the reference-feedback diagnostic."""
    yield 'selected_requirement',design
    for name,reason,changes in (
        ('uniform_timing_control','Equal-duration SAR timing control',{
            'model_assumptions.paired_sar.parameters.bit_durations_s':[1.8e-9]*10}),
        ('combined_slow_probe','Combined slower DAC and weaker reference-buffer hypothesis',{
            'model_assumptions.paired_sar.parameters.dac_tau_s':.4e-9,
            'blocks.refbuf.parameters.output_r_ohm':100.,
            'blocks.refbuf.parameters.reservoir_f':50e-12}),
        ('slow_dac_probe','Slower DAC settling hypothesis',{
            'model_assumptions.paired_sar.parameters.dac_tau_s':.8e-9})):
        yield name,design.hypothetical(reason=reason,changes=changes)


def converter_feedback(contract,*,design=None):
    """Close RF -> trial bits -> reference current -> PDN -> RF iteratively."""
    from design_definition import DesignDefinition,Scenario
    design=design_for_contract(contract,design)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario(wanted_dbm=-65.,blocker_dbm=-30.).override(
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl,
            reason='Package uncertainty case: '+label)
        for name,variant in converter_design_cases(design):
            config=variant.configure(engine='rf',direction='rx',reference_hz=2.484e9,
                sample_divider=64,pga_gain_db=max(variant.architecture['blocks']['pga_i']['parameters']['gain_db']))
            e=configured_environment(config,scenario)
            parameters=environment_converter_parameters(e)
            response=None;iterations=[];converged=False
            for iteration in range(4):
                current=e if response is None else dict(e,local_load_response=response)
                capture={}
                rx=wideband_receive(current,oversample=max(256,minimum_envelope_oversample(current)),wanted_dbm=scenario.wanted_dbm,blocker_dbm=scenario.blocker_dbm,gain_settings_db=(config.pga_gain_db,),
                    sar_parameters=parameters,load_capture=capture)
                updated,load=load_response(capture,e['network'],reference_supply_parameters=reference_supply_parameters(e),
                    delay_pole_hz=clock_supply_delay_pole(e),sensitivity_ps_per_mv=clock_supply_sensitivity(e))
                rms_delta,maximum_delta,converged=response_change(updated,response)
                iterations.append(dict(iteration=iteration,load_response=load,
                    feedback_rail_rms_change_v=rms_delta,feedback_rail_maximum_change_v=maximum_delta,
                    observation=rx['gain_cases'][0]['observation']))
                response=updated
                if converged:break
            owner=rx['gain_cases'][0]['adc']
            resolution=None
            if name=='selected_requirement':
                _,fine_load=load_response(capture,e['network'],grid_s=.125e-9,reference_supply_parameters=reference_supply_parameters(e),
                    delay_pole_hz=clock_supply_delay_pole(e),sensitivity_ps_per_mv=clock_supply_sensitivity(e))
                resolution=dict(coarse=load,fine=fine_load,
                    scope='Same final reference-current trajectory on two PDN grids. This checks the load waveform, not an additional closed-loop RF refinement.')
            rows.append(dict(design_provenance=variant.provenance(),resolved_configuration=config.record(),
                scenario_overrides=scenario.record(),stimuli=scenario.stimulus_record(),
                model_simplifications=['Electrical seed clock spectrum and rail-only load feedback; no differential input-return root recomputation in this diagnostic.'],
                network_case=label,parameters_case=name,receiver=rx,
                converter_precision=[tone_precision(e,parameters,bin_number=k) for k in (53,499)],
                load_grid_resolution=resolution,
                iterations=iterations,numerical_feedback_converged=converged,
                reference_owner_reserved_a=e['inventory_current_report']['by_block_ma']['refbuf']/1000,
                reference_average_reservation_margin_a=e['inventory_current_report']['by_block_ma']['refbuf']/1000-owner['reference_with_bias_average_a'],
                scope='Highest selected sample rate, same -65 dBm wanted/-30 dBm blocker and fixed maximum supported PGA gain. Reference source AC current is recomputed from each pass, fed through the same PDN, and applied to RF gain/headroom, LO/sample timing and reference target on the next pass. The current inventory DC reservation is retained; a positive average reference margin is not a peak-current or physical-headroom proof and is not charged a second time. Convergence limits (1 uV RMS / 20 uV peak rail change) are numerical diagnostics, not silicon tolerances. No ADC comparator-regeneration, DAC-TX load or full noise/variation qualification.'))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Closed behavioral reference-load feedback under assigned device dynamics. Slower poles are uncertainty probes, not measured process corners. This supplements rather than relabels the retained assigned-ENOB RF/packet cases.')


def transmitter_wake_campaign(contract,*,design=None):
    """Join the already-budgeted driver transition to actual RF observations."""
    from design_definition import DesignDefinition,Scenario
    design=design_for_contract(contract,design)
    config=design.configure(engine='rf',direction='tx',reference_hz=2.484e9,sample_divider=64)
    bias=design.architecture['blocks']['rfdriver']['parameters']['bias_current_a']
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario(reference_peak_v=.5).override(package_return_inductance_h=return_l,
            die_decoupling_esl_h=die_esl,reason='Package uncertainty case: '+label)
        e=configured_environment(config,scenario)
        context=dict(resolved_configuration=config.record(),scenario_overrides=scenario.record())
        e,clock=reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
        if e is None:
            rows.append(dict(context,network_case=label,clock=clock,status='clock_rejected',cases=[]))
            continue
        cases=[]
        for released,lead,ramp in ((0.,0.,20e-9),(.25*bias,0.,20e-9),(bias,0.,20e-9),
                                   (.25*bias,2e-6,20e-9),(bias,2e-6,20e-9),(bias,2e-6,1e-6)):
            response,load=driver_wake_response(e,released_current_a=released,
                wake_start_s=2e-6-lead,ramp_s=ramp,grid_s=.5e-9)
            current=dict(e,local_load_response=response)
            cases.append(dict(lead_before_waveform_s=lead,load=load,
                transmitter=wideband_transmit(current,oversample=max(256,minimum_envelope_oversample(current)))))
        # Repeat the fastest, full-current simultaneous launch with finer PDN
        # sampling. All waveform/noise seeds remain identical.
        response,load=driver_wake_response(e,released_current_a=bias,wake_start_s=2e-6,grid_s=.25e-9)
        fine=dict(load=load,transmitter=wideband_transmit(dict(e,local_load_response=response),oversample=max(256,minimum_envelope_oversample(e))))
        _,long_guard=driver_wake_response(e,released_current_a=bias,wake_start_s=2e-6,grid_s=.5e-9,guard_s=16e-6)
        rows.append(dict(context,network_case=label,carrier_hz=e['carrier_hz'],clock=clock,cases=cases,resolution_control=fine,guard_control=long_guard))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Warm, partial and full driver wake hypotheses within the same architecture-derived maximum mode allocation. Corrected REF_IN clock and coupled local-load transfer include direct input-voltage perturbations, supply delay and returned carrier. Guarded FFT response uses 0.5/0.25 ns grids and 8/16 us guard controls; ideal linear-ramp corners make peak estimates resolution-sensitive. Host ripple, moving reference, clock crossings and RF port observation are joined. These are bounded load transitions, not a transistor prediction or proof of analog wake readiness. Known DATA training can hide early transient damage; real preamble acquisition and emissions remain open.')


def wired_transmit_transport(environment,*,host_service_ppm=0.,frames=512,
                             reference_stop_s=None,chunks=None):
    """Existing finite host bridge consumed at actual delivered TX word events.

    Return a bounded first waveform window separately from serializable evidence.
    D2H uses the declared divide-by-eight relationship; FPGA sees only delayed
    elapsed edges. It cannot inspect FIFO state or future TX event times.
    """
    from behavioral import Assumptions,BehavioralChip
    from selected_rf import DeliveredClock
    if environment['payload_engine']!='wire' or environment['carrier_hz']!=2.5e9:
        raise ValueError('This joined transport fixture requires the 2.5 GHz wired environment')
    config=environment.get('resolved_configuration')
    if config is not None and (config['engine']!='wire' or config['direction'] not in ('tx','duplex')
            or config['line_rate_bps']!=2.5e9 or config['host_word_hz']!=312.5e6):
        raise ValueError('Resolved configuration must match this 2.5 Gb/s, divide-by-eight transport fixture')
    if type(frames) is not int or frames<1 or not math.isfinite(host_service_ppm) or abs(host_service_ppm)>1000:
        raise ValueError('Positive frame count and bounded host service offset required')
    if reference_stop_s is not None and (not math.isfinite(reference_stop_s) or reference_stop_s<=0):
        raise ValueError('Positive finite observed-reference stop time required')
    chunks=(frames,) if chunks is None else tuple(chunks)
    if any(type(n) is not int or n<1 for n in chunks) or sum(chunks)!=frames:
        raise ValueError('Chunks must partition the declared positive frame count')
    # TX consumes the receiver-side (egress) queue of the framed host link.
    # Half-full startup is a bench policy, not another hardware allocation.
    parameters=environment.get('transport_parameters',{})
    depth=parameters.get('legacy_tx_queue_bits')
    if type(depth) is not int or depth<20:
        raise ValueError('Wired transport requires shared legacy TX queue capacity')
    if not isinstance(parameters.get("queue_status"),str):
        raise ValueError("Wired transport requires shared queue allocation status")
    prefill=depth//2
    from selected_lifecycle import selected_transport_assumptions
    assumptions=selected_transport_assumptions(environment)
    assumptions=replace(assumptions,h2d_clock_scale=assumptions.h2d_clock_scale*(1+host_service_ppm*1e-6))
    chip=BehavioralChip(assumptions)
    chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
    chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
    # transfer(frames=...) counts nominal mode-1 frame durations. H2D
    # service rate is independently applied through assumptions above; changing
    # that rate must not shorten the precomputed TX/reference event horizon.
    origin=chip.time;duration=frames*64/312.5e6;clock=DeliveredClock(environment)
    word_count=math.ceil(duration*250e6)+16
    ideal_words=origin+np.arange(1,word_count+1)/250e6
    word_events=ideal_words+clock.crossing_error(ideal_words,2.5e9)-origin
    ideal_forward=origin+np.arange(math.ceil(duration*312.5e6)+16)/312.5e6
    forward=ideal_forward+clock.crossing_error(ideal_forward,2.5e9)
    expected=np.random.default_rng(9021).integers(0,2,prefill+10*(word_count+128)).tolist()
    initial=sum(int(b)<<j for j,b in enumerate(expected[:prefill]))
    def source(index):
        offset=prefill+10*index
        return sum(int(b)<<j for j,b in enumerate(expected[offset:offset+10]))
    def ticks(time):
        observed=time-2/312.5e6
        if reference_stop_s is not None:observed=min(observed,origin+reference_stop_s)
        return int(np.searchsorted(forward,observed,side='right'))
    emitted=[]
    def emit(time,word):emitted.append((time,word))
    arguments=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,directions=('tx',),
        tx_source=source,tx_prefill_bits=prefill,tx_prefill_value=initial,depth_bits=depth,
        host_block_words=8,host_cdc_read_hz=40e6,host_cdc_phase=.37,
        tx_reference_pacing=True,tx_reference_ticks=ticks,tx_word_observer=emit,
        tx_event_time=lambda index:float(word_events[index]))
    for count in chunks:
        flow=chip.transfer(frames=count,**arguments)
        if flow['fault'] is not None:break
    actual=[(word>>j)&1 for _,word in emitted for j in range(10)]
    errors=sum(a!=b for a,b in zip(actual,expected))
    event_error=max((abs(time-origin-word_events[i]) for i,(time,_) in enumerate(emitted)),default=0.)
    trace=None
    if len(actual)>=2600:
        anchor=origin+1/250e6
        ideal=anchor+np.arange(2601)/2.5e9
        edges=ideal+clock.crossing_error(ideal,2.5e9)-anchor
        np.testing.assert_allclose([time-anchor for time,_ in emitted[:260]],edges[:-1:10],rtol=0.,atol=1e-15)
        trace=dict(bits=actual[:2600],edges_s=edges,absolute_origin_s=anchor)
    report=dict(design_provenance=deepcopy(environment.get('design_provenance')),
        resolved_configuration=deepcopy(config),scenario_overrides=deepcopy(environment.get('scenario_overrides',[])),
        scenario_assumptions=deepcopy(environment.get('scenario_assumptions',{})),
        startup_guard_s=assumptions.startup_s,transport_started_at_s=origin,
        transport_fixture=dict(queue_depth_bits=depth,prefill_bits=prefill,
            prefill_policy="half_capacity_floor",queue_owner="transport.scheduling.egress_bits_per_source",
            queue_status=parameters["queue_status"]),
        host_service_ppm=host_service_ppm,requested_frames=frames,
        reference_stop_s=reference_stop_s,flow=flow,chip_state=chip.state,
        emitted_words=len(emitted),payload_bit_errors=errors,
        peer_waveform_window_bits=0 if trace is None else len(trace['bits']),
        host_service_offset_changes_ac_spectrum=False,
        emitted_bits_sha256=hashlib.sha256(bytes(actual)).hexdigest(),
        maximum_word_event_error_s=event_error,transport_allocation='exclusive_59_of_64',
        scope='Shared legacy egress planning queue with half-capacity prefill, eight-word staging and ideal two-stage CDC at 40 MHz. Word consumption uses corrected shared-environment TX edges; forwarded pacing counts the same clock divided by eight with assigned two-word observation delay. Host ppm varies service only; AC host harmonics remain nominal, so this is not an asynchronous interference envelope. No new storage architecture or occupancy oracle. Only the first 2600 emitted bits feed the peer window; transport identity extends over the full run. Startup ready and prefill are assumed; reference halt tests logical underflow, not physical pad muting/recovery. Complete storage inventory, physical CDC, supply-dependent logic delay and driver-current feedback remain open.')
    return report,trace


def wired_transmit_campaign(contract,*,source_peak_v=1.,include_swing_controls=True,design=None):
    """Delivered TX edges through a finite channel to an independent peer CDR."""
    from selected_rf import DeliveredClock
    from design_definition import DesignDefinition,Scenario
    design=design_for_contract(contract,design)
    config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario(reference_peak_v=source_peak_v).override(
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl,
            reason='Package uncertainty case: '+label)
        original=configured_environment(config,scenario)
        context=dict(resolved_configuration=config.record(),scenario_overrides=scenario.record(),
            scenario_assumptions=dict(scenario.assumptions),stimuli=scenario.stimulus_record())
        e,clock=reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=source_peak_v)
        if e is None:
            rows.append(dict(context,network_case=label,clock=clock,status='tx_clock_rejected',receiver=None))
            continue
        ideal=np.arange(2601)/2.5e9
        error=DeliveredClock(e).crossing_error(ideal,2.5e9);edges=ideal+error
        rail=e['ledger']['local_payload_clock_core_rail_v']
        peer=dict(name=label,delay_tones=[],signal_scale=rail/wired_gain_reference(e),rail_dc_v=rail,
            rail_tones=e['host_spectrum']['tones'],rail_modulation_location='driver',
            ctle_zero_s=200e-12,ctle_pole_s=80e-12)
        received=causal_receiver_envelope(timing_scenarios=[peer],channel_cases=((2.7e-12,100e-12),),source_edges_s=edges)
        ideal_control=causal_receiver_envelope(timing_scenarios=[peer],channel_cases=((2.7e-12,100e-12),))
        transport_cases=[]
        for ppm in (-100.,100.):
            transport,trace=wired_transmit_transport(e,host_service_ppm=ppm)
            if trace is not None:
                shifted=dict(peer,rail_tones=[dict(t,voltage_phase_rad=t['voltage_phase_rad']+
                    2*math.pi*t['frequency_hz']*trace['absolute_origin_s']) for t in peer['rail_tones']])
                transport['peer']=causal_receiver_envelope(timing_scenarios=[shifted],
                    channel_cases=((2.7e-12,100e-12),),source_edges_s=trace['edges_s'],source_bits=trace['bits'])
            transport_cases.append(transport)
        halted,_=wired_transmit_transport(e,host_service_ppm=-100.,reference_stop_s=5e-6)
        phase_controls=[]
        if label==BASELINE_PACKAGE_CASE:
            # Nominal H2D physical clock is /16 of TX bits. Ten-bit word
            # boundaries visit eight even-bit phases of that coherent period.
            # This discrete launch grid is not a continuous/asynchronous bound.
            for offset_ui in range(0,16,2):
                origin=offset_ui/2.5e9
                if offset_ui==0:
                    observed=received;shifted=peer;shifted_edges=edges
                else:
                    absolute=origin+ideal
                    shifted_edges=absolute+DeliveredClock(e).crossing_error(absolute,2.5e9)-origin
                    shifted=dict(peer,rail_tones=[dict(t,voltage_phase_rad=t['voltage_phase_rad']+
                        2*math.pi*t['frequency_hz']*origin) for t in peer['rail_tones']])
                    observed=causal_receiver_envelope(timing_scenarios=[shifted],
                        channel_cases=((2.7e-12,100e-12),),source_edges_s=shifted_edges)
                mean_shift=float(np.mean(shifted_edges-ideal))
                constant=causal_receiver_envelope(timing_scenarios=[shifted],
                    channel_cases=((2.7e-12,100e-12),),source_edges_s=ideal+mean_shift)
                phase_controls.append(dict(launch_offset_ui=offset_ui,origin_s=origin,receiver=observed,
                    constant_mean_clock_control=constant,constant_clock_shift_s=mean_shift))
        rows.append(dict(context,network_case=label,clock=clock,status='tx_channel_exercised',receiver=received,
            finite_transport_cases=transport_cases,reference_halt_transport=halted,
            nominal_word_launch_phase_controls=phase_controls,
            nominal_launch_phase_summary=None if not phase_controls else dict(
                cases=sum(len(p['receiver']['cases']) for p in phase_controls),
                continuously_qualified_cases=sum(c['heldout_qualified_fraction']==1. and c['final_timing_qualified']
                    for p in phase_controls for c in p['receiver']['cases']),
                constant_clock_all_qualified=all(c['heldout_qualified_fraction']==1. and c['final_timing_qualified']
                    for p in phase_controls for c in p['constant_mean_clock_control']['cases']),
                scope='Eight nominal word-launch phases times four peer corners; not an asynchronous phase bound or a chip-completeness count.'),
            ideal_tx_clock_control=ideal_control,
            all_heldout_data_errors_zero=all(c['heldout_errors']==0 for c in received['cases']),
            all_heldout_continuously_qualified=all(c['heldout_qualified_fraction']==1. and c['final_timing_qualified'] for c in received['cases']),
            edge_count=len(edges),edge_sha256=hashlib.sha256(edges.astype('<f8').tobytes()).hexdigest(),
            centered_tx_edge_rms_s=float(np.std(error)),mean_tx_edge_shift_s=float(np.mean(error)),
            minimum_tx_ui_s=float(min(np.diff(edges))),
            rx_clock_owner='independent_peer_cdr',tx_phase_applied_to_peer_aperture=False))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,source_peak_v=source_peak_v,
        source_swing_controls=[wired_transmit_campaign(contract,source_peak_v=swing,include_swing_controls=False,design=design)
            for swing in (.75,1.)] if include_swing_controls else [],
        scope='2.5 Gb/s NRZ source boundaries use corrected loaded REF_IN timing, assigned source/input noise and correlated supply delay. Rail-proportional NRZ drive propagates through persistent driver/load/CTLE state using exact sinusoidal forcing between actual bit edges; it is not multiplied onto the channel output. The assigned drive/rail law still needs device evidence. Direct-source controls are supplemented by finite host transport and eight nominal word-launch phases at the current package target. Only a short emitted window feeds the independent peer; 1200 held-out bits per phase/ppm corner are not BER qualification. No shared-clock cancellation. Internal serializer setup/hold, continuous/asynchronous host phase, driver-current feedback, pad nonlinearities, cable loss and protocol compliance remain open.')


def wired_gain_reference(environment):
    """Characterization voltage, distinct from the actual board source."""
    parameters=environment.get('wired_supply_gain_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound wired model missing gain reference voltage')
        return 3.3  # Independent legacy numerical fixture.
    value=parameters['reference_voltage_v']
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
        raise ValueError('Positive finite wired gain reference voltage required')
    return value


def wired_shared_impairment(environment):
    """Local RX sensitivity to shared rails, independent of TX REF_IN phase.

    Aperture sensitivity is an assigned local CDR requirement owned by the
    shared inventory. Remote signal timing and recovered RX clock remain independent.
    """
    if environment['payload_engine']!='wire':raise ValueError('Wired environment required')
    parameters=environment.get('cdr_supply_delay_parameters')
    if parameters is None:
        if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
            raise ValueError('Design-bound wired RX missing CDR supply-delay parameters')
        parameters=dict(supply_sensitivity_ps_per_mv=.1,delay_pole_hz=1e9)
    sensitivity=parameters['supply_sensitivity_ps_per_mv']*1e-9
    pole=parameters['delay_pole_hz']
    rail=environment['ledger']['local_payload_clock_core_rail_v'];tones=[]
    for t in environment['host_spectrum']['tones']:
        h=sensitivity/(1+1j*t['frequency_hz']/pole)
        tones.append(dict(frequency_hz=t['frequency_hz'],delay_peak_s=float(t['clock_rail_voltage_peak_v']*abs(h)),
            delay_phase_rad=float(t['voltage_phase_rad']+np.angle(h))))
    return dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02,
        delay_tones=tones,signal_scale=rail/wired_gain_reference(environment),rail_dc_v=rail,rail_tones=environment['host_spectrum']['tones'])


def wired_receiver_inventory(environment):
    """Resolve the shared pad's balanced scalar reduction and nominal equalizer."""
    cap=np.asarray(environment['wired_pad_capacitance_f'],dtype=float)
    if cap.shape!=(2,2) or not np.all(np.isfinite(cap)):
        raise ValueError('Finite two-leg pad capacitance matrix required')
    if not np.allclose(cap,cap.T,rtol=1e-12,atol=1e-24) or np.min(np.linalg.eigvalsh(cap))<=0:
        raise ValueError('Symmetric positive-definite pad capacitance matrix required')
    odd=np.array([1.,-1.]);odd_cap=float(odd@cap@odd/2)
    if odd_cap<=0 or not np.allclose(cap@odd,odd_cap*odd,rtol=1e-12,atol=1e-24):
        raise ValueError('Scalar wired recovery requires a symmetric odd-mode pad; use a coupled-pad solver')
    ctle=environment['wired_ctle_parameters']
    cdr=environment['wired_cdr_parameters']
    controls={}
    if cdr.get('detector_model')=='early_late':
        if environment.get('wired_tracking_sampler_count')!=4:
            raise ValueError('Selected window detector requires four tracking samplers')
        controls={key:cdr[key] for key in ('detector_model','phase_gain','frequency_gain','frequency_slope_gain',
            'detector_window_ui','detector_wide_window_ui','detector_widen_after_ui',
            'gap_frequency_boost','gap_frequency_boost_after_ui','holdover_residual_ppm')}
        controls['bound_aperture_motion']=True
    elif cdr.get('detector_model')=='phase_bank':
        bins=cdr['detector_phase_bins']
        if environment.get('wired_tracking_sampler_count',0)<bins+2:
            raise ValueError('Phase bank requires every sampler slot')
        controls={key:cdr[key] for key in ('detector_model','detector_phase_bins','detector_phase_span_ui',
            'phase_gain','frequency_gain','frequency_slope_gain','holdover_residual_ppm')}
        controls.update(bound_aperture_motion=True,
            periodic_clock_compute_delay_s=cdr.get('periodic_clock_compute_delay_s'),
            periodic_observation_link=cdr.get('periodic_observation_link'),
            period_control_lsb_ppm=cdr.get('period_control_lsb_ppm',0.),
            phase_control_steps=cdr.get('phase_control_steps',0),
            acquisition_ui=cdr.get('acquisition_timeout_ui',1024))
    elif 'design_provenance' in environment:
        raise ValueError('Design-bound receiver requires an explicit supported detector')
    return dict(controls,pad_cap_f=odd_cap,ctle_zero_s=ctle['zero_s'],
        ctle_pole_s=ctle['pole_s'],ctle_dc_gain=ctle['dc_gain'],
        detector_noise_rms_s=environment['wired_cdr_parameters']['detector_jitter_rms_s'],
        holdover_ui=environment['wired_cdr_parameters']['holdover_bits'])



def baseline_wired_receiver_inputs(environment, *, label):
    """Shared hardware with explicit reduced-channel baseline stimuli."""
    parameters=wired_receiver_inventory(environment)
    impairment=wired_shared_impairment(environment)
    impairment.update({key:value for key,value in parameters.items()
        if key not in ('pad_cap_f','ctle_dc_gain')})
    impairment['signal_scale']*=parameters['ctle_dc_gain']
    impairment['name']=label
    return dict(timing_scenario=impairment,
        channel_case=(parameters['pad_cap_f'],100e-12),
        receiver_inventory=parameters,
        probe_assumptions={'source_response_s':100e-12,
            'channel_model':'Balanced scalar pad with 50 ohm reduced source load',
            'voltage_noise_rms_v':.01,'voltage_offset_v':.02})


def wired_recovery_campaign(contract,*,design=None):
    """Existing ordered host/recovery lifecycle with the selected analog RX."""
    from behavioral import raw_host_alignment_controls
    from design_definition import DesignDefinition,Scenario
    design=design_for_contract(contract,design)
    config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario(reference_peak_v=.5).override(
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl,
            reason='Package uncertainty case: '+label)
        e=configured_environment(config,scenario)
        context=dict(resolved_configuration=config.record(),scenario_overrides=scenario.record(),
            scenario_assumptions=dict(scenario.assumptions),stimuli=scenario.stimulus_record())
        e,clock=reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
        if e is None:
            rows.append(dict(context,network_case=label,clock=clock,ctle_zero_s=None,ctle_pole_s=None,
                verdict=dict(completed=False,failure='TX reference clock rejected for full-duplex baseline; RX-only capability not assessed by this gate'),
                lifecycle=None,analog_diagnostics=[]))
            continue
        impairment=wired_shared_impairment(e)
        receiver_parameters=wired_receiver_inventory(e)
        odd_cap=receiver_parameters['pad_cap_f']
        impairment.update({key:value for key,value in receiver_parameters.items()
            if key not in ('pad_cap_f','ctle_dc_gain','ctle_zero_s','ctle_pole_s')})
        ctle=e['wired_ctle_parameters']
        for factor in (None,.75,1.):
            zero=None if factor is None else factor*ctle['zero_s']
            selected_impairment=dict(impairment)
            if zero is not None:
                selected_impairment.update(ctle_zero_s=zero,ctle_pole_s=ctle['pole_s'])
                selected_impairment['signal_scale']*=ctle['dc_gain']
            for remote,host in ((100.,-100.),(-100.,100.)):
                receivers=[]
                def factory(bits,rate,phase,ppm):
                    rx=physical_receiver(bits,rate,phase,ppm,100e-12,odd_cap,selected_impairment,hold_final_level=True)
                    receivers.append(rx)
                    return rx
                try:
                    lifecycle=raw_host_alignment_controls(host_clock_gap=True,
                        remote_clock_ppm=remote,host_clock_ppm=host,source_factory=factory,
                        publication_hz=e['control_hz']*(1+host*1e-6))
                    enough=all(c['minimum_release_met'] for c in lifecycle['cases'])
                    verdict=dict(completed=True,minimum_release_met=enough,
                        failure=None if enough else 'Insufficient validated frames after acquisition/recovery')
                except ValueError as error:
                    # A bounded transport failure is evidence, not a reason to omit
                    # the case or silently substitute a larger buffer. Programming
                    # errors and unrelated validation exceptions still propagate.
                    if str(error)!='Bit/event stream overflow':raise
                    lifecycle=None
                    verdict=dict(completed=False,failure=str(error),
                        stopped_at_committed_bit=receivers[-1].bit_index,
                        elapsed_source_s=receivers[-1].last_timestamp)
                diagnostics=[]
                for rx in receivers:
                    rails=rx.rail_observations
                    diagnostics.append(dict(observed_rail_interval_v=[min(rails),max(rails)],
                        rail_observations_outside_legacy_fixture=sum(not 2.5<=v<=3.6 for v in rails),
                        first_qualified_bit=rx.first_qualified_bit,qualification_losses=rx.qualification_losses,
                        committed_bits=rx.bit_index))
                rows.append(dict(context,network_case=label,pad_cap_f=odd_cap,switch_tau_s=100e-12,
                    receiver_fixture=dict(remote_source_switch_tau_s=100e-12,load_resistance_ohm=50.,
                        ctle_zero_factor=factor,role='nominal_equalizer' if factor==1 else 'diagnostic_equalizer_control',
                        scope='Balanced odd-mode pad reduction; equalizer bypass/reduced-zero controls are diagnostic substitutions, not asserted selectable configurations.'),
                    cdr_supply_delay_parameters=dict(e['cdr_supply_delay_parameters']),
                    receiver_inventory=dict(receiver_parameters),
                    clock=clock,rx_clock_owner='independent_cdr',tx_reference_phase_applied_to_rx=False,
                    remote_clock_ppm=remote,host_clock_ppm=host,verdict=verdict,
                    ctle_zero_s=selected_impairment.get('ctle_zero_s'),ctle_pole_s=selected_impairment.get('ctle_pole_s'),
                    lifecycle=lifecycle,analog_diagnostics=diagnostics))
    ctle=design.architecture['blocks']['ctle']['parameters']
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,selected_ctle=dict(zero_s=ctle['zero_s'],pole_s=ctle['pole_s'],dc_gain=ctle['dc_gain'],high_frequency_gain=ctle['dc_gain']*ctle['zero_s']/ctle['pole_s']),
        scope='Selected architecture current allocation with corrected coupled REF_IN loading and returned carrier on the shared rails. TX reference rejection gates full-duplex cases, not RX-only capability. RX aperture uses assigned local supply sensitivity independently of TX reference phase; supply-proportional local RX gain joins causal CDR, bounded raw/status transport and FPGA marker framing. Independent +/-100 ppm host/line clocks, line gaps, host-clock halt and explicit restart. Reference-presence pulses and independent watchdog are lifecycle stimuli, not a qualified clock monitor. No SATA ALIGN, PCIe LTSSM, USB electrical lifecycle or protocol qualification. Physical clock distribution, analog pad transitions and host GPIO timing remain open.')


def host_source_parameters(environment):
    """Resolve host loading without defaults for an intended-chip environment."""
    h=environment['host_spectrum']
    if any(key in environment for key in ('design_provenance','inventory_current_report','resolved_configuration')):
        for key in ('inventory_current_a','inventory_current_report'):
            if key not in environment:
                raise ValueError('Design-bound host source missing '+key)
        for key in ('output_cap_f','output_voltage_v','d2h_internal_charge_c','internal_charge_c',
                    'd2h_word_hz','h2d_word_hz','d2h_internal_tau_s'):
            if key not in h:
                raise ValueError('Design-bound host source missing '+key)
            value=h[key]
            strictly_positive=key.endswith('word_hz') or key in ('d2h_internal_tau_s','output_voltage_v')
            if (isinstance(value,bool) or not isinstance(value,(int,float))
                    or not math.isfinite(value) or value<0
                    or strictly_positive and value==0):
                raise ValueError('Design-bound host source invalid '+key)
    return h


def pad_ground_tones(environment):
    """Recover the same host sources at die return, relative to board return."""
    from robustness_envelope import host_harmonic_current,h2d_current_ports,shared_return_transfer
    e=environment;s=host_source_parameters(e);n=e['network']
    common=dict(return_r=n['return_r_ohm'],return_l=n['return_l_h'],**n['network'])
    ground={}
    for harmonic in range(1,s.get('d2h_harmonics',12)+1):
        f=harmonic*s['d2h_word_hz']/2
        current=host_harmonic_current(f,s['d2h_word_hz'],harmonic,s['d2h_internal_tau_s'],output_cap_f=s.get('output_cap_f',10e-12),internal_charge_c=s.get('d2h_internal_charge_c',7e-12),output_voltage_v=s.get('output_voltage_v',3.3))
        ground[f]=current*shared_return_transfer(f,**common)['ground_ohm']
    for harmonic in range(1,s.get('h2d_harmonics',6)+1):
        f=harmonic*s['h2d_word_hz']/2
        currents=h2d_current_ports(f,s['h2d_word_hz'],harmonic,
            internal_charge_c=s['internal_charge_c'],alternating=s['alternating'],origin_s=s['h2d_origin_s'])
        internal=shared_return_transfer(f,injection_weights=(0.,-1.,1.),**common)
        external=shared_return_transfer(f,injection_weights=(0.,0.,s['external_return_fraction']),**common)
        ground[f]=ground.get(f,0j)+currents['chip_internal_peak_a']*internal['ground_ohm']+currents['external_cap_return_peak_a']*external['ground_ohm']
    for f,ports in internal_switching_sources(e.get('internal_switching_loads',()),owner_current_a=e.get('inventory_current_a')).items():
        # Both internal owners draw from local VDD and return to the tied die ground.
        transfer=shared_return_transfer(f,injection_weights=(0.,-1.,1.),**common)
        ground[f]=ground.get(f,0j)+ports[3]*transfer['ground_ohm']
    return ground


def usb_static_output(environment,ledger,*,levels,load_ohm,load_supply_v=0.):
    """Static two-leg voltage drive with coherent moving local rail and return.

    Pad C is to die return; test resistors terminate at the board fixture.
    This is a necessary voltage screen, not transitions or USB qualification.
    """
    from protocol_pad import SharedWiredPad
    cap=np.asarray(environment['wired_pad_capacitance_f'],dtype=float)
    levels=np.array(levels,dtype=float)
    try:
        drive_r=environment['wired_usbfs_parameters']['effective_output_r_ohm']
    except KeyError as exc:
        raise ValueError('USB voltage screen requires shared FS driver resistance') from exc
    if isinstance(drive_r,bool) or not isinstance(drive_r,(int,float)) or not math.isfinite(drive_r) or drive_r<=0:
        raise ValueError('USB FS driver resistance must be finite and positive')
    conductance=np.eye(2)*(1/drive_r+1/load_ohm)
    dc=np.linalg.solve(conductance,levels*ledger['local_payload_clock_core_rail_v']/drive_r+
        np.full(2,(load_supply_v-ledger['die_return_v'])/load_ohm))+ledger['die_return_v']
    ground=pad_ground_tones(environment);legs=[[],[]]
    for tone in environment['host_spectrum']['tones']:
        f=tone['frequency_hz'];rail=tone['clock_rail_voltage_peak_v']*np.exp(1j*tone['voltage_phase_rad'])
        g=ground[f]
        v=np.linalg.solve(2j*np.pi*f*cap+conductance,levels*rail/drive_r-np.full(2,g/load_ohm))+g
        for i in (0,1):legs[i].append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(v[i])),voltage_phase_rad=float(np.angle(v[i]))))
    intervals=[]
    for tones,value in zip(legs,dc):
        result=rail_excursion(tones,dc_v=float(value),samples_per_fastest_period=128)
        intervals.append({k:result[k] for k in ('sampled_interval_v','enclosed_interval_v',
            'grid_enclosure_error_v','samples','period_s')})
    context={key:deepcopy(environment[key]) for key in (
        'design_provenance','resolved_configuration','scenario_overrides',
        'scenario_assumptions','operating_conditions','diagnostic_intervention') if key in environment}
    return dict(**context,levels=levels.tolist(),driver_ohm=drive_r,test_load_ohm=load_ohm,
        model_role='shared_design_affine_static_pad',dc_ledger=deepcopy(ledger),
        diagnostic_assumptions=dict(driver_law='affine_resistive_voltage_source',
            external_load_ohm=load_ohm,external_load_supply_v=load_supply_v,
            voltage_scope='Supplied DC ledger; AC spectra retained from the configured environment'),
        test_supply_v=load_supply_v,dc_output_v=dc.tolist(),
        legs=intervals)


def usb_voltage_campaign(contract,*,design=None):
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario().override(reason='USB static-voltage package comparison',
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
        e,context=usb_supply_environment(design,scenario=scenario)
        for wire_current in dict.fromkeys((e['inventory_current_a']['wire'],.096,.050)):
            for source in (3.267,3.2835,3.3,3.333):
                ledger=selected_dc_ledger('wire',e['network'],source_v=source,wire_current_a=wire_current,owner_current_a=e['inventory_current_a'],
                    h2d_internal_a=e['host_spectrum']['chip_h2d_internal_mean_a'])
                high=usb_static_output(e,ledger,levels=(1,0),load_ohm=15000.)
                low=usb_static_output(e,ledger,levels=(0,0),load_ohm=1500.,load_supply_v=3.6)
                h=high['legs'][0];l=low['legs'][0]
                rows.append(dict(context,probe_assumptions=dict(board_source_v=source,
                    wire_current_override_a=None if wire_current==e['inventory_current_a']['wire'] else wire_current,
                    current_scope='Explicit DC load substitution for sensitivity; other owners retain shared allocations',
                    voltage_scope='DC source change only; AC spectra stay at nominal voltage'),network_case=label,wire_current_a=wire_current,ledger=ledger,
                    high=high,low=low,observed_high_below_2p8v=h['sampled_interval_v'][0]<2.8,
                    enclosed_high_above_2p8v=h['enclosed_interval_v'][0]>=2.8,
                    enclosed_high_below_3p6v=h['enclosed_interval_v'][1]<=3.6,
                    enclosed_low_below_0p3v=l['enclosed_interval_v'][1]<=.3))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        source='USB 2.0 section 7.1.1 and Table 7-7: high >=2.8 V into 15 kohm; low <=0.3 V with 1.5 kohm to 3.6 V. https://www.seriesten.org/docs/protocols/USB_2.0_Specification.pdf',
        scope='Shared USB inventory and host-follow rates, with explicit 96 mA/50 mA DC wire-owner load substitutions alongside the nominal allocation. These substitutions are diagnostic stimuli, not newly legal hardware current budgets. Die-return motion is included in board-referenced pad voltage. Nominal-source AC spectra retained at DC source corners. Static affine driver/capacitance and resistive compliance loads only; no signal-bond inductance, cable, edge-rate control, switching injection, pad-current PDN feedback, voltage-dependent drive or complete USB lifecycle.')



def usb_rate_feasibility_audit(*,design=None):
    """Audit retained analog rate evidence; do not rerun or relabel its provenance."""
    path=P/'evidence/selected-baseline.json';source=json.loads(path.read_text())
    from robustness_envelope import shared_return_transfer
    design=load_design() if design is None else design
    e,context=usb_supply_environment(design)
    before=pad_ground_tones(e)
    e['internal_switching_loads']=[dict(owner='timing',mean_a=.010,event_hz=156.25e6,tau_s=.2e-9,harmonics=64),
        dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
    after=pad_ground_tones(e);bounds=np.zeros(2);n=e['network']
    for f,value in after.items():
        increment=value-before.get(f,0j)
        transfer=hs_pad_transfer(f,capacitance_f=e['wired_pad_capacitance_f'])
        z=shared_return_transfer(f,return_r=n['return_r_ohm'],return_l=n['return_l_h'],injection_weights=(0.,0.,1.),**n['network'])
        loaded=increment/(1+z['ground_ohm']*sum(transfer['ground_board'])/45.)
        bounds+=abs(transfer['ground_board']*loaded)
    cancellation_bound=float(max(bounds))
    rows=[]
    for case in source['usb_hs_levels']['host_rate_controls']:
        if case['network_case']!=BASELINE_PACKAGE_CASE:continue
        for transport in case['transport']:
            crossings=[]
            for label,clock in (('word_rate_destination_hypothesis',case['word_hz']),('control_rate_destination_hypothesis',case['control_hz'])):
                delay=3/clock
                total=transport['incomplete_roundtrip_bound_s']+delay
                crossings.append(dict(destination_hypothesis=label,destination_hz=clock,additional_d2h_visibility_s=delay,
                    roundtrip_with_d2h_s=total,remaining_response_margin_s=transport['response_limit_s']-total,
                    response_bound_met=total<=transport['response_limit_s'],
                    all_listed_necessary_conditions_met=bool(total<=transport['response_limit_s'] and transport['capacity_covers_480mbps'] and case['quiet_pin_instantaneous_guard_met'])))
            rows.append(dict(word_hz=case['word_hz'],frame_words=transport['frame_words'],
                payload_capacity_bps=transport['payload_capacity_bps'],capacity_covers_480mbps=transport['capacity_covers_480mbps'],
                quiet_pin_enclosed_abs_peak_v=case['quiet_pin_enclosed_abs_peak_v'],quiet_pin_guard_met=case['quiet_pin_instantaneous_guard_met'],
                quiet_pin_peak_lower_bound_with_arbitrary_internal_phase_v=None,
                combination_status='not_combined_historical_host_sweep_and_current_usb_inventory',
                historical_context={key:case[key] for key in ('design_provenance','resolved_configuration','scenario_overrides') if key in case},
                original_incomplete_roundtrip_s=transport['incomplete_roundtrip_bound_s'],response_limit_s=transport['response_limit_s'],d2h_hypotheses=crossings))
    return dict(cases=rows,current_internal_current_diagnostic=dict(context,
        internal_loads=e['internal_switching_loads'],internal_pad_ac_amplitude_sum_bound_v=bounds.tolist(),
        maximum_internal_pad_bound_v=cancellation_bound,
        pad_fixture_assumptions=dict(termination_ohm=[45.,45.],bond_l_h=[2e-9,2e-9],bond_r_ohm=.2)),
        historical_source_provenance=source.get('design_provenance'),
        input_evidence_sha256={str(path.relative_to(P)):hashlib.sha256(path.read_bytes()).hexdigest()},
        scope='Audit of historical no-added-internal-current USB host-rate controls at the current package target; original source provenance is retained in the input artifact. Add an explicit three-destination-cycle D2H visibility hypothesis to the previously H2D-only bound. Word-rate versus control-rate destinations are alternatives awaiting implementation ownership, not measured latency. The current shared USB configuration supplies a separate internal-tone amplitude diagnostic. It is not subtracted from historical host-only peaks: their design, rates and package assumptions have not been established as identical. Historical timing arithmetic and screening flags describe only the retained source cases, not the current chip. No cable, additional physical timing margin, real FPGA/CDC event simulation or added-current analog sweep. All-necessary-conditions flag is a screening conjunction, never qualification; 20 mV instantaneous pad guard is not a complete USB compliance test.')


def usb_supply_environment(design,*,scenario=None):
    """USB endpoint inventory and selected host-follow rates for supply probes."""
    from design_definition import Scenario
    config=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
        host_clock_source='host_follow',host_input_hz=design.architecture['direct_stream_service']['budget']['host_hz'],
        wired_pad_path='bidirectional')
    scenario=Scenario() if scenario is None else scenario
    return configured_environment(config,scenario),dict(design_provenance=design.provenance(),
        resolved_configuration=config.record(),scenario_overrides=scenario.record(),
        host_spectrum_scope='Existing DDR-shaped harmonic surrogate at configured host rates; not qualified SDR switching')


def usb_internal_campaign(contract,*,design=None):
    """Static HS pad obligations under unchanged host and added internal AC loads."""
    design=design_for_contract(contract,design)
    rows=[]
    for scale in (0.,.5,1.):
        e,context=usb_supply_environment(design)
        e['internal_switching_loads']=[dict(owner='timing',mean_a=.010*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64),
            dict(owner='core',mean_a=.020*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)] if scale else []
        ledger=partitioned_dc_ledger(e,dict(link_r_ohm=1e-5))
        for name,termination,bonds in (('matched',(45.,45.),(2e-9,2e-9)),('asymmetric',(42.75,47.25),(1.6e-9,2.4e-9))):
            states=[usb_hs_output(e,ledger,drive_node=drive,termination_ohm=termination,bond_l_h=bonds) for drive in (None,0,1)]
            rows.append(dict(context,pad_fixture_assumptions=dict(termination_ohm=termination,bond_l_h=bonds),load_scale=scale,fixture=name,ledger=ledger,internal_loads=e['internal_switching_loads'],states=states))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,scope='Static USB HS pad states under shared USB inventory and configured host-follow switching. Internal timing/core pulse means replace portions of their shared owner allocations. 156.25 MHz internal pulses are assigned stress loads, not a USB clock implementation. Two signal bonds, local/remote terminations and pad-return feedback included. No REF_IN current, signal-dependent driver loading, real edges, squelch/chirp, packet lifecycle or protocol qualification. 20 mV quiet-pin value is the existing instantaneous design guard; observer-bandwidth controls are diagnostic, not a compliance instrument.')


def hs_pad_transfer(frequency_hz, *, termination_ohm=(45.,45.),
                    bond_l_h=(2e-9,2e-9), bond_r_ohm=.2,capacitance_f=None):
    """Board-referenced two-leg pad, with local C and separate signal bonds.

    Linear local 45-ohm terminations return to die ground; the precision peer
    terminations return to board ground. Numeric asymmetry is a hypothesis.
    Returns board voltage per die-ground voltage and per local current source.
    Omitted capacitance uses an independent primitive example, never a disk
    reload. Intended-chip callers must supply their environment-owned matrix.
    """
    from protocol_pad import SharedWiredPad
    if not math.isfinite(frequency_hz) or frequency_hz<0 or not math.isfinite(bond_r_ohm) or bond_r_ohm<=0:
        raise ValueError('Nonnegative frequency and positive bond resistance required')
    if len(termination_ohm)!=2 or len(bond_l_h)!=2 or any(not math.isfinite(x) or x<=0 for x in termination_ohm) or any(not math.isfinite(x) or x<0 for x in bond_l_h):
        raise ValueError('Two positive terminations and nonnegative inductances required')
    cap=SharedWiredPad().C if capacitance_f is None else np.asarray(capacitance_f,dtype=float)
    if cap.shape!=(2,2) or not np.all(np.isfinite(cap)) or not np.allclose(cap,cap.T,rtol=1e-12,atol=0.) or np.min(np.linalg.eigvalsh(cap))<=0:
        raise ValueError('Finite symmetric positive-definite two-leg pad capacitance required')
    w=2*np.pi*frequency_hz
    local=1j*w*cap+np.diag(1/np.array(termination_ohm))
    bond=bond_r_ohm+1j*w*np.array(bond_l_h)
    peer=1/45.;to_board=1/(1+peer*bond)
    matrix=local+np.diag(peer*to_board)
    ground_die=np.linalg.solve(matrix,local@np.ones(2))
    current_die=np.linalg.solve(matrix,np.eye(2))
    return dict(ground_board=to_board*ground_die,
        current_board=to_board[:,None]*current_die,
        ground_die=ground_die,current_die=current_die)


def usb_hs_output(environment,ledger,*,drive_node=None,termination_ohm=None,
                  bond_l_h=(2e-9,2e-9),bond_r_ohm=.2):
    """Static HS levels under host switching, including pad-to-PDN feedback.

    The two precision remote loads form additional paths from die ground to
    board ground. Close that linear loop; don't impose unloaded ground motion.
    Current steering is ideal while in compliance, inside the existing WIRE
    reservation. No packet, edge, comparator or negotiation pass is implied.
    """
    from robustness_envelope import shared_return_transfer
    if drive_node not in (None,0,1):raise ValueError('Released or physical P/N leg required')
    e=environment;n=e['network'];peer=1/45.
    parameters=environment['wired_usb_parameters']
    for key in ('drive_current_a','termination_ohm_per_leg'):
        value=parameters[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite shared USB output parameters required')
    if termination_ohm is None:termination_ohm=(parameters['termination_ohm_per_leg'],)*2
    options=dict(termination_ohm=termination_ohm,bond_l_h=bond_l_h,bond_r_ohm=bond_r_ohm,
        capacitance_f=environment['wired_pad_capacitance_f'])
    dc=hs_pad_transfer(0.,**options);injection=np.zeros(2)
    if drive_node is not None:injection[drive_node]=parameters['drive_current_a']
    # The source current is already inside the mode budget. Redirect its
    # externally returned portion; never add a second pad load to the ledger.
    offset=(dc['current_board']@injection).real
    gain=dc['ground_board'].real;rg=n['return_r_ohm']
    ground_dc=(ledger['die_return_v']-rg*peer*sum(offset))/(1+rg*peer*sum(gain))
    board_dc=gain*ground_dc+offset
    die_local_dc=(dc['ground_die']*ground_dc+dc['current_die']@injection).real-ground_dc
    ground=pad_ground_tones(e);legs=[[],[]];differential=[];feedback=[]
    for f,g in ground.items():
        transfer=hs_pad_transfer(f,**options)
        z=shared_return_transfer(f,return_r=rg,return_l=n['return_l_h'],
            injection_weights=(0.,0.,1.),**n['network'])
        admittance=peer*sum(transfer['ground_board'])
        loaded=g/(1+z['ground_ohm']*admittance)
        board=transfer['ground_board']*loaded
        for i in (0,1):legs[i].append(dict(frequency_hz=f,
            clock_rail_voltage_peak_v=float(abs(board[i])),voltage_phase_rad=float(np.angle(board[i]))))
        diff=board[0]-board[1]
        differential.append(dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(diff)),voltage_phase_rad=float(np.angle(diff))))
        feedback.append(dict(frequency_hz=f,unloaded_ground_peak_v=float(abs(g)),
            loaded_ground_peak_v=float(abs(loaded)),pad_return_current_peak_a=float(abs(admittance*loaded)),
            local_rail_correction_peak_v=float(abs(z['differential_ohm']*admittance*loaded))))
    intervals=[rail_excursion(t,dc_v=float(v),samples_per_fastest_period=128) for t,v in zip(legs,board_dc)]
    quiet=[i for i in (0,1) if i!=drive_node]
    observed=max(max(abs(x) for x in intervals[i]['sampled_interval_v']) for i in quiet)
    enclosed=max(max(abs(x) for x in intervals[i]['enclosed_interval_v']) for i in quiet)
    # Sufficient uniform reduction of host-induced AC current, preserving its
    # frequency/phase pattern and the constant allocation. Not a free remedy.
    allowances=[]
    for i in quiet:
        lo,hi=intervals[i]['enclosed_interval_v'];center=board_dc[i]
        ac=max(center-lo,hi-center)
        allowances.append(max(0.,(.020-abs(center))/ac) if ac else 1.)
    bandwidth_controls=[]
    for pole in (20e6,200e6,1e9):
        filtered=[]
        for i in quiet:
            tones=[]
            for t in legs[i]:
                h=1/(1+1j*t['frequency_hz']/pole)
                tones.append(dict(t,clock_rail_voltage_peak_v=t['clock_rail_voltage_peak_v']*abs(h),
                    voltage_phase_rad=t['voltage_phase_rad']+float(np.angle(h))))
            filtered.append(rail_excursion(tones,dc_v=float(board_dc[i]),samples_per_fastest_period=128))
        peak=max(max(abs(x) for x in item['enclosed_interval_v']) for item in filtered)
        bandwidth_controls.append(dict(single_pole_observer_hz=pole,
            quiet_pin_enclosed_abs_peak_v=peak,within_20mv=peak<=.020))
    context={key:deepcopy(environment[key]) for key in (
        'design_provenance','resolved_configuration','scenario_overrides',
        'scenario_assumptions','operating_conditions','diagnostic_intervention') if key in environment}
    return dict(**context,drive_node=drive_node,drive_current_a=float(sum(injection)),
        dc_ledger=deepcopy(ledger),
        diagnostic_assumptions=dict(current_source='ideal_constant_current',
            quiet_pin_guard_v=.020,remote_termination_ohm=45.),
        model_role='shared_design_ideal_current_static_pad',
        assigned_drive_current_a=parameters['drive_current_a'],
        termination_override=tuple(termination_ohm)!=(parameters['termination_ohm_per_leg'],)*2,
        local_termination_ohm=list(termination_ohm),remote_termination_ohm=45.,
        signal_bond_l_h=list(bond_l_h),signal_bond_r_ohm=bond_r_ohm,
        loaded_dc_ground_v=float(ground_dc),board_dc_v=board_dc.tolist(),
        die_local_dc_v=die_local_dc.tolist(),legs=intervals,
        differential=rail_excursion(differential,dc_v=float(board_dc[0]-board_dc[1]),samples_per_fastest_period=128),
        pad_to_pdn_feedback=feedback,observer_bandwidth_controls=bandwidth_controls,
        quiet_pin_observed_abs_peak_v=observed,quiet_pin_enclosed_abs_peak_v=enclosed,
        quiet_pin_dc_within_20mv=all(abs(board_dc[i])<=.020 for i in quiet),
        quiet_pin_instantaneous_guard_met=enclosed<=.020,
        sufficient_host_ac_scale_for_20mv=min(1.,*allowances))


def usb_hs_level_campaign(contract,*,design=None):
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[];rate_controls=[]
    for label,return_l,die_esl in network_cases(design):
        scenario=Scenario().override(reason='USB HS pad package comparison',
            package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
        e,context=usb_supply_environment(design,scenario=scenario)
        ledger=partitioned_dc_ledger(e,dict(link_r_ohm=1e-5))
        nominal_termination=e['wired_usb_parameters']['termination_ohm_per_leg']
        for fixture,termination,bonds in (
            ('matched_no_signal_inductance_control',(nominal_termination,)*2,(0.,0.)),
            ('matched_2nh_signal_bonds',(nominal_termination,)*2,(2e-9,2e-9)),
            ('asymmetric_termination_and_bonds',(.95*nominal_termination,1.05*nominal_termination),(1.6e-9,2.4e-9))):
            rows.append(dict(context,pad_fixture_assumptions=dict(termination_ohm=termination,bond_l_h=bonds),network_case=label,fixture=fixture,ledger=ledger,
                states=[usb_hs_output(e,ledger,drive_node=node,termination_ohm=termination,bond_l_h=bonds)
                        for node in (None,0,1)]))
        # Diagnostic rescheduling only: regenerate both directional host-current
        # spectra at each candidate rate. No claim that other clock consumers,
        # physical GPIO timing or a variable-rate control ABI are qualified.
        from protocol_pad import usb_framed_turnaround
        for word_hz in (312.5e6,300e6,281.25e6,275e6,267.5e6,250e6,200e6,156.25e6,125e6,100e6,78.125e6,62.5e6):
            candidate=dict(e,host_spectrum=dict(e['host_spectrum'],
                d2h_word_hz=word_hz,h2d_word_hz=word_hz,
                d2h_harmonics=math.ceil(12*312.5e6/word_hz),
                h2d_harmonics=math.ceil(6*312.5e6/word_hz)))
            candidate['diagnostic_intervention']=dict(host_word_hz=word_hz,
                scope='Spectral-rate substitution only; retained configuration identifies the parent design')
            current=(11*e['host_spectrum']['internal_charge_c']*word_hz)
            dc=selected_dc_ledger('wire',e['network'],source_v=e['board_source_v'],owner_current_a=e['inventory_current_a'],h2d_internal_a=current)
            pad=usb_hs_output(candidate,dc)
            transport=[]
            for frame_words in (8,64):
                bound=usb_framed_turnaround(frame_words=frame_words,word_hz=word_hz,
                    h2d_cdc_hz=word_hz/8)
                transport.append(dict(frame_words=frame_words,
                    payload_capacity_bps=bound['raw_payload_capacity_bps'],
                    capacity_covers_480mbps=bound['raw_payload_capacity_bps']>=480e6,
                    incomplete_roundtrip_bound_s=bound['worst_s'],
                    response_limit_s=bound['maximum_s'],
                    incomplete_response_bound_met=bound['meets_bound'],
                    assumptions=bound['assumptions']))
            rate_controls.append(dict(context,diagnostic_intervention=dict(host_word_hz=word_hz,
                scope='Overrides spectral rates and legacy framed timing only; not a resolved legal host configuration'),network_case=label,word_hz=word_hz,
                physical_ddr_clock_hz=word_hz/2,control_hz=word_hz/8,ledger=dc,
                d2h_harmonics=candidate['host_spectrum']['d2h_harmonics'],
                h2d_harmonics=candidate['host_spectrum']['h2d_harmonics'],
                quiet_pin_observed_abs_peak_v=pad['quiet_pin_observed_abs_peak_v'],
                quiet_pin_enclosed_abs_peak_v=pad['quiet_pin_enclosed_abs_peak_v'],
                quiet_pin_instantaneous_guard_met=pad['quiet_pin_instantaneous_guard_met'],
                observer_bandwidth_controls=pad['observer_bandwidth_controls'],
                transport=transport,
                any_frame_meets_all_necessary_guards=any(
                    t['capacity_covers_480mbps'] and t['incomplete_response_bound_met'] and
                    pad['quiet_pin_instantaneous_guard_met'] for t in transport)))
    return dict(design_provenance=design.provenance(),cases=rows,host_rate_controls=rate_controls,complete=False,
        source='USB-IF USB 2.0 Electrical Compliance Test Specification v1.07 EL_9 and section 4.3: undriven high-speed pin voltage with precision 45-ohm loads. https://www.usb.org/sites/default/files/USB%202%200%20Electrical%20Compliance%20Specification(v1.07).pdf',
        rate_control_scope='Counterfactual D2H/H2D rate substitutions, unchanged host transition charges, pulse shapes, total current reservation and package. Recompute internal-current location and harmonic frequencies, retaining at least the original absolute frequency coverage (1.875 GHz D2H, 937.5 MHz H2D); control follows H2D physical clock /4. Eight- and 64-word frame calculations include only the existing H2D CDC budget; D2H CDC, cable and physical timing margins remain missing, so a passing number cannot qualify turnaround. Slower rates are not adopted architecture settings.',
        scope='Both host and device use the same local electrical branch. Released/J/K static conditions at shared USB host-follow rates and current inventory, board-referenced peer loads, local inactive capacitance and signal bonds. Termination return current closes into the common PDN at every host harmonic. DC and unfiltered instantaneous +/-20 mV guards are reported separately, with explicitly hypothetical single-pole observer bandwidth controls; none establishes the correct compliance instrument response. Asymmetry values are sensitivity probes, not process tolerances. No transmission line, current-source output impedance/noise/supply dependence, switched drive, transient readiness, real comparator or FPGA negotiation lifecycle.')


def partitioned_return_solution(frequency_hz, candidate, injection, *,
        common_fraction=.1, link_r_ohm=None, coupling_f=20e-12,
        host_cap_fraction=0., host_return_share=.5, quiet_load_s=0j):
    """Five-node requirement model: feed, quiet supply, host/quiet/board returns.

    Two weighted return branches in parallel plus the common segment reproduce
    the original R/L when host and quiet grounds are shorted. No extra terminal
    count or qualified ground partition is implied. Total local C is conserved.
    """
    if not math.isfinite(frequency_hz) or frequency_hz<0 or not 0<common_fraction<1 or not 0<=host_cap_fraction<1 or not 0<host_return_share<1:
        raise ValueError('Nonnegative frequency, bounded common segment and cap partition required')
    if not math.isfinite(coupling_f) or coupling_f<0 or (link_r_ohm is not None and (not math.isfinite(link_r_ohm) or link_r_ohm<=0)):
        raise ValueError('Passive inter-return coupling required')
    source=np.asarray(injection,dtype=complex)
    if source.shape!=(5,) or not np.all(np.isfinite(source)) or not np.isfinite(quiet_load_s) or quiet_load_s.real<0:
        raise ValueError('Five finite current injections and passive quiet load required')
    n=candidate['network'];w=2*np.pi*frequency_hz;m=np.zeros((5,5),complex);branches=[]
    def branch(a,b,y):
        m[a,a]+=y
        if b is not None:m[b,b]+=y;m[a,b]-=y;m[b,a]-=y
        branches.append((a,b,y))
    def capacitor(c,r,l):return 0j if not frequency_hz or not c else 1/(r+1j*w*l+1/(1j*w*c))
    branch(0,None,1/(n['feed_r']+1j*w*n['feed_l']))
    branch(0,1,1/(n['package_r']+1j*w*n['package_l']))
    branch(0,None,capacitor(n['board_c'],n['board_esr'],n['board_esl']))
    total=candidate['return_r_ohm']+1j*w*candidate['return_l_h']
    branch(2,4,host_return_share/((1-common_fraction)*total))
    branch(3,4,(1-host_return_share)/((1-common_fraction)*total))
    branch(4,None,1/(common_fraction*total))
    branch(2,3,(0. if link_r_ohm is None else 1/link_r_ohm)+1j*w*coupling_f)
    for fraction,a,b in ((1-host_cap_fraction,1,3),(host_cap_fraction,0,2)):
        if fraction:
            branch(a,b,capacitor(n['die_c']*fraction,n.get('die_esr',0.)/fraction,n.get('die_esl',0.)))
    branch(3,None,quiet_load_s)
    v=np.linalg.solve(m,source)
    power=float(np.real(np.vdot(v,source))/2)
    dissipated=sum(abs(v[a]-(0 if b is None else v[b]))**2*y.real/2 for a,b,y in branches)
    return dict(voltage=v,kcl_residual_a=float(max(abs(m@v-source))),
        power_residual_w=float(power-dissipated))



def internal_switching_sources(loads,*,owner_current_a=None):
    """AC ports for positive gamma-shaped pulses, within existing DC budgets.

    Each event draws Q*t**2*exp(-t/tau)/(2*tau**3), Q=mean/rate.
    CORE and timing already own 40 mA each at local VDD/quiet return.
    Only their AC Fourier components are added here; steady remainder plus
    pulse mean replaces, rather than supplements, each owner's DC allocation.
    These are assigned load hypotheses, not inferred GF180 current waveforms.
    """
    totals={'core':0.,'timing':0.};sources={}
    budget=MODE_CURRENT_A['rf'] if owner_current_a is None else owner_current_a
    for load in loads:
        owner=load['owner'];mean=load['mean_a'];rate=load['event_hz']
        tau=load['tau_s'];origin=load.get('origin_s',0.);count=load['harmonics']
        if owner not in totals:raise ValueError('Unknown internal-current owner')
        if not all(math.isfinite(x) for x in (mean,rate,tau,origin)) or mean<0 or rate<=0 or tau<=0:
            raise ValueError('Invalid internal-current pulse parameters')
        if type(count) is not int or not 1<=count<=256:raise ValueError('Invalid harmonic count')
        totals[owner]+=mean
        if totals[owner]>budget[owner]+1e-15:raise ValueError('Internal pulse mean exceeds owner DC budget')
        for k in range(1,count+1):
            f=k*rate
            current=2*mean*np.exp(-2j*np.pi*f*origin)/(1+2j*np.pi*f*tau)**3
            sources[f]=sources.get(f,np.zeros(5,complex))+np.array([0,-current,0,current,0])
    return sources


def adc_pair_current_allocation(environment):
    """Current ADC pair allocation; the shared network node grants no transfers."""
    report=environment['inventory_current_report']
    if report['mode']!='rf_rx':
        raise ValueError('ADC activity requires the RF receive allocation')
    return sum(report['by_block_ma'][name] for name in ('adc_i','adc_q'))/1000


def partitioned_d2h_sources(environment):
    """D2H port currents shared by full forcing and stopped-clock subtraction."""
    from robustness_envelope import host_harmonic_current
    h=host_source_parameters(environment);sources={}
    for k in range(1,h.get('d2h_harmonics',12)+1):
        f=k*h['d2h_word_hz']/2
        current=host_harmonic_current(f,h['d2h_word_hz'],k,h['d2h_internal_tau_s'],
            output_cap_f=h.get('output_cap_f',10e-12),internal_charge_c=h.get('d2h_internal_charge_c',7e-12),output_voltage_v=h.get('output_voltage_v',3.3))
        sources[f]=np.array([-current,0,current,0,0])
    return sources


def partitioned_host_sources(environment, input_at_feed=False):
    """Host charges plus optional budgeted core/timing switching ports."""
    from robustness_envelope import h2d_current_ports
    h=host_source_parameters(environment);sources=partitioned_d2h_sources(environment)
    def add(f,vector):sources[f]=sources.get(f,np.zeros(5,complex))+vector
    for k in range(1,h.get('h2d_harmonics',6)+1):
        f=k*h['h2d_word_hz']/2
        c=h2d_current_ports(f,h['h2d_word_hz'],k,internal_charge_c=h['internal_charge_c'],
            alternating=h['alternating'],origin_s=h['h2d_origin_s'])
        v=np.zeros(5,complex);v[0 if input_at_feed else 1]-=c['chip_internal_peak_a']
        v[2]+=c['chip_internal_peak_a']+h['external_return_fraction']*c['external_cap_return_peak_a']
        add(f,v)
    for f,vector in internal_switching_sources(environment.get('internal_switching_loads',()),
                                             owner_current_a=environment.get('inventory_current_a')).items():
        add(f,vector)
    if 'adc_switching' in environment:
        from converter_dynamics import adc_switching_sources
        adc=environment['adc_switching'];parameters=environment_converter_parameters(environment)
        if 'inventory_current_report' in environment and adc['mean_a']>adc_pair_current_allocation(environment)+1e-15:
            raise ValueError('ADC switching exceeds its own block allocation')
        assigned=sum(load['mean_a'] for load in environment.get('internal_switching_loads',()) if load['owner']=='core')
        if assigned+adc['mean_a']+parameters.reference_idle_a+parameters.reference_limit_a>environment['ledger']['owner_current_a']['core']+1e-15:
            raise ValueError('ADC switching exceeds remaining CORE allocation')
        for f,vector in adc_switching_sources(**adc,parameters=parameters).items():add(f,vector)
    return sources

def clock_screen_environment(design, mode, carrier, *, scenario=None,sample_divider=64):
    """Shared direct-clock operating point for RF/wired supply screens."""
    from design_definition import Scenario
    settings=dict(engine=mode,direction='rx',reference_hz=carrier)
    if mode=='rf':settings.update(sample_divider=sample_divider,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    else:settings['host_divider']=8
    config=design.configure(**settings);scenario=Scenario() if scenario is None else scenario
    return configured_environment(config,scenario),dict(design_provenance=design.provenance(),
        resolved_configuration=config.record(),scenario_overrides=scenario.record())


def internal_switching_campaign(contract,*,design=None):
    """Fast shared-clock screen; no packet or infinite-bandwidth claim."""
    design=design_for_contract(contract,design)
    rows=[]
    for mode,carrier,word in (('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)):
        original,context=clock_screen_environment(design,mode,carrier)
        for scale in (0.,.5,1.):
            for count in ((32,) if scale==0 else (32,64)):
                loads=[dict(owner='timing',mean_a=.010*scale,event_hz=carrier/16,tau_s=.2e-9,harmonics=count),
                    dict(owner='core',mean_a=.020*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=count)]
                e=dict(original,internal_switching_loads=loads if scale else [])
                _,report=reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=.75)
                rows.append(dict(context,source_differential_peak_v=.75,mode=mode,carrier_hz=carrier,load_scale=scale,harmonics=count,
                    loads=loads if scale else [],clock=report))
    return dict(design_provenance=design.provenance(),cases=rows,scope='Assigned positive pulse loads replace portions of CORE/timing DC allocations; nominal coherent phases, positive supply sensitivity, current package target and 0.75 V source. 32/64 harmonic comparison only, not a bounded infinite-frequency tail or packet verdict. No full-rate clock switching, delivered-edge/load feedback, phase sweep or physical pulse characterization.')


def internal_pulse_campaign(contract,*,design=None):
    """Current differential input with explicit pulse shape and phase hypotheses."""
    design=design_for_contract(contract,design)
    rows=[]
    variants=[(.2e-9,phase,64) for phase in (0.,.25,.5,.75)]+[(tau,0.,64) for tau in (.1e-9,.4e-9)]+[(.1e-9,0.,128)]
    for mode,carrier,word in (('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)):
        for tau,phase,harmonics in variants:
            original,context=clock_screen_environment(design,mode,carrier)
            loads=[dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=tau,harmonics=harmonics),
                dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=tau,harmonics=harmonics,origin_s=phase/156.25e6)]
            original['internal_switching_loads']=loads
            _,clock=reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=.75,sensitivity_ps_per_mv=.1)
            e=clock['resolved_crossings'];a=e['centered_edge_error_rms_ps'];d=e['downstream_delay_rms_at_edges_ps'];total=e['combined_edge_error_rms_ps']
            covariance=None if None in (a,d,total) else (total**2-a**2-d**2)/2
            correlation=None if covariance is None or a*d==0 else covariance/(a*d)
            rows.append(dict(context,source_differential_peak_v=.75,mode=mode,carrier_hz=carrier,loads=loads,tau_s=tau,core_phase_cycles=phase,harmonics=harmonics,
                clock=clock,input_downstream_covariance_ps2=covariance,input_downstream_correlation=correlation))
            print('Internal pulse',mode,carrier,tau,phase,harmonics,flush=True)
    return dict(design_provenance=design.provenance(),cases=rows,scope='500 pF baseline, 0.25 nH package target, 0.75 V source and unchanged mean budgets. Timing/core switched means 10/20 mA; vary common gamma-pulse time constant and core origin relative to fixed timing/host activity. Not a full width-by-phase sweep, independent clock phase proof or physical pulse bounds. Same-edge input error/downstream-delay covariance is a diagnostic, not independent noise addition. 64/128 harmonics compared only for the sharpest zero-phase case. No payload qualification.')


def internal_sensitivity_campaign(contract,*,design=None):
    """Exact variance rescaling of freshly simulated deterministic edge components.

    Source currents and input roots stay fixed; only downstream sensitivity is
    scaled, with its 1 GHz pole unchanged. This is not a payload approximation.
    """
    design=design_for_contract(contract,design)
    source=internal_pulse_campaign(contract,design=design)
    rows=[];checks=[]
    for case in source['cases']:
        if case['tau_s']!=.2e-9 or case['harmonics']!=64:continue
        e=case['clock']['resolved_crossings'];a=e['centered_edge_error_rms_ps'];d=e['downstream_delay_rms_at_edges_ps']
        context={key:case[key] for key in ('design_provenance','resolved_configuration','scenario_overrides','loads')}
        covariance=case['input_downstream_covariance_ps2']
        if any(value is None for value in (a,d,covariance)):
            rows.append(dict(context,status='unavailable_edge_covariance',clock=case['clock']))
            continue
        values=[]
        for sensitivity in (0.,.025,.05,.1,.2):
            for sign in ((1.,) if sensitivity==0 else (-1.,1.)):
                scale=sign*sensitivity/.1
                variance=a*a+scale*scale*d*d+2*scale*covariance
                if variance < -1e-10:raise ValueError('Invalid stored covariance')
                values.append(dict(signed_sensitivity_ps_per_mv=sign*sensitivity,edge_rms_ps=math.sqrt(max(0.,variance))))
        rows.append(dict(context,mode=case['mode'],carrier_hz=case['carrier_hz'],core_phase_cycles=case['core_phase_cycles'],values=values))
        if case['core_phase_cycles']==.75:
            carrier=case['carrier_hz'];word=carrier/16 if case['mode']=='rf' else 312.5e6
            original,replay_context=clock_screen_environment(design,case['mode'],carrier)
            original['internal_switching_loads']=case['loads']
            _,actual=reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=.75,supply_sign=-1.,sensitivity_ps_per_mv=.1)
            predicted=next(v['edge_rms_ps'] for v in values if v['signed_sensitivity_ps_per_mv']==-.1)
            observed=actual['resolved_crossings']['combined_edge_error_rms_ps']
            if abs(predicted-observed)>1e-8:raise AssertionError((predicted,observed))
            checks.append(dict(replay_context,loads=case['loads'],mode=case['mode'],carrier_hz=carrier,predicted_edge_rms_ps=predicted,clock=actual))
    return dict(design_provenance=design.provenance(),cases=rows,negative_sign_replays=checks,input_source='internal_pulse_campaign computed in this run with the current differential input',
        scope='Conditional scalar downstream sensitivity at fixed 1 GHz pole, source currents and input roots. Exact variance identity includes covariance. Four freshly simulated coherent core phases, 0.2 ns pulses and baseline package/capacitance only. Negative 0.1 ps/mV replay verifies three cases. No circuit-achievable bound, arbitrary phase coverage, edge-order validation for extrapolated scales, payload, protocol jitter-mask or random-noise qualification.')


def decoupling_environment(design,mode,carrier,cap,esr,esl):
    from design_definition import Scenario
    nominal=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']
    changes={f'blocks.power.parameters.reduced_pdn_model.network.{key}':value
             for key,value in (('die_c',cap),('die_esr',esr)) if value!=nominal[key]}
    variant=design.hypothetical(reason='Decoupling capacitance/damping circuit experiment',changes=changes) if changes else design
    scenario=Scenario()
    if esl!=nominal['die_esl']:
        scenario=scenario.override(reason='Decoupling parasitic uncertainty',die_decoupling_esl_h=esl)
    return clock_screen_environment(variant,mode,carrier,scenario=scenario)


def internal_decoupling_campaign(contract, *, damping=False,design=None):
    """Cost-visible capacitance screen at unchanged package and load hypotheses."""
    design=design_for_contract(contract,design)
    nominal_cap=design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['die_c']
    rows=[]
    cases=([(1e-9,r,200e-12) for r in (.25,.5,1.,2.)]+[(1e-9,.5,l) for l in (100e-12,400e-12)]
        if damping else [(c,.5,200e-12) for c in (500e-12,1e-9,2e-9)])
    for mode,carrier,word in (('rf',2.4e9,150e6),('rf',2.484e9,155.25e6),('wire',2.5e9,312.5e6)):
        for cap,esr,esl in cases:
            original,context=decoupling_environment(design,mode,carrier,cap,esr,esl)
            original['internal_switching_loads']=[
                dict(owner='timing',mean_a=.010,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
                dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)]
            trial,clock=reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=.75)
            rail=None
            if trial is not None:
                phasors={}
                for t in trial['host_spectrum']['tones']:
                    f=t['frequency_hz'];v=t['clock_rail_voltage_peak_v']*np.exp(1j*t['voltage_phase_rad'])
                    phasors[f]=phasors.get(f,0j)+v
                bound=sum(abs(v) for v in phasors.values());dc=trial['ledger']['local_payload_clock_core_rail_v']
                rail=dict(conservative_interval_v=[dc-bound,dc+bound],ac_rms_v=float(np.sqrt(sum(abs(v)**2 for v in phasors.values())/2)))
            rows.append(dict(context,internal_switching_loads=original['internal_switching_loads'],source_differential_peak_v=.75,mode=mode,carrier_hz=carrier,die_cap_f=cap,die_esr_ohm=esr,die_esl_h=esl,
                capacitor_area_multiplier_at_fixed_density=cap/nominal_cap,clock=clock,rail=rail))
            print('Decoupling screen',mode,carrier,cap,esr,esl,flush=True)
    return dict(design_provenance=design.provenance(),cases=rows,scope='Explicit capacitance/ESR/ESL cases, 0.25 nH package target, existing mean current and full internal pulse hypothesis. Passive-network sensitivity: no physical area/ESR/ESL realization, phase sweep, payload or infinite-tail qualification. Rail interval is a conservative coherent-tone amplitude-sum bound, not sampled extrema. No baseline hardware selection changes.')


def internal_switching_rf_campaign(contract,*,design=None):
    """Matched wideband/SAR feedback controls at sufficient rail-tone bandwidth."""
    design=design_for_contract(contract,design)
    rows=[]
    for carrier in (2.4e9,2.484e9):
        for scale in (0.,1.):
            loads=[dict(owner='timing',mean_a=.010*scale,event_hz=carrier/16,tau_s=.2e-9,harmonics=64),
                dict(owner='core',mean_a=.020*scale,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)] if scale else []
            original,context=clock_screen_environment(design,'rf',carrier)
            original['internal_switching_loads']=loads
            e,clock=reference_payload_environment(original,dict(link_r_ohm=1e-5),False,source_peak_v=.75)
            receiver=None if e is None else coupled_wideband_feedback(e,wanted_dbm=-85.,gain_db=context['resolved_configuration']['pga_gain_db'],oversample=max(1024,minimum_envelope_oversample(e)))
            rows.append(dict(context,scenario_stimuli=dict(wanted_dbm=-85.,blocker_dbm=-30.,source_differential_peak_v=.75),carrier_hz=carrier,load_scale=scale,loads=loads,clock=clock,receiver=receiver))
            print('RF internal switching',carrier,scale,'complete',flush=True)
    return dict(design_provenance=design.provenance(),cases=rows,scope='Current differential reference input and package target, 0.75 V source-amplitude probe, architecture-derived DC budget; positive supply sensitivity and nominal coherent internal-current phases. Matched 20.48 GHz numerical mixer rate resolves retained tones through 10 GHz; no infinite-tail convergence claim. Weak wanted signal plus adjacent blocker, causal SAR/reference-current feedback, the current PGA maximum and known DATA training. No real acquisition, AGC, packet/PER or physical device qualification.')


def return_partition_campaign(contract,*,design=None):
    """Compare routing hypotheses at unchanged charge, rate, current and C."""
    from robustness_envelope import host_harmonic_current,h2d_current_ports,supply_delay_tones
    from oscillator_noise import PhaseNoise
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[]
    sites=contract['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
    host_sites=[site for side in ('north','south') for site in sites[side] if 'vss_pads[' in site]
    quiet_sites=[site for side in ('east','west') for site in sites[side] if 'vss_pads[' in site]
    host_share=len(host_sites)/(len(host_sites)+len(quiet_sites))
    variants=(
        ('tied_control',dict(link_r_ohm=1e-5),False),
        ('split_return_only',dict(),False),
        ('split_return_host_input_supply',dict(),True),
        ('split_return_and_reservoir',dict(host_cap_fraction=.25),True),
        ('half_reservoir_at_host',dict(host_cap_fraction=.5),True),
        ('three_quarter_reservoir_at_host',dict(host_cap_fraction=.75),True),
        ('lower_interreturn_capacitance',dict(host_cap_fraction=.5,coupling_f=2e-12),True),
        ('two_host_eight_quiet_site_hypothesis',dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=host_share),True),
        ('larger_interreturn_capacitance',dict(host_cap_fraction=.25,coupling_f=100e-12),True),
        ('larger_common_segment',dict(host_cap_fraction=.25,common_fraction=.5),True),
        ('conductive_interreturn_coupling',dict(host_cap_fraction=.25,link_r_ohm=1.),True))
    for mode,carrier,word in (('wire',2.5e9,312.5e6),('rf',2.4e9,2.4e9/16),('rf',2.484e9,2.484e9/16)):
        for label,return_l,die_esl in network_cases(design):
            scenario=Scenario().override(reason='Return-routing package comparison',
                package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
            e,context=clock_screen_environment(design,mode,carrier,scenario=scenario)
            n=e['network'];h=e['host_spectrum']
            for name,overrides,move_input in variants:
                options=dict(common_fraction=.1,link_r_ohm=None,coupling_f=20e-12,host_cap_fraction=0.,host_return_share=.5)
                options.update(overrides)
                sources=partitioned_host_sources(e,move_input)
                internal=0. if move_input else e['host_spectrum']['chip_h2d_internal_mean_a']
                ledger=selected_dc_ledger(mode,n,source_v=e['board_source_v'],owner_current_a=e['inventory_current_a'],h2d_internal_a=internal)
                dc_source=np.array([ledger['source_v']/n['network']['feed_r']-ledger['host_node_current_a'],
                    -ledger['local_branch_current_a'],ledger['owner_current_a']['host'],ledger['total_chip_supply_current_a']-ledger['owner_current_a']['host'],0.])
                pad_dc=hs_pad_transfer(0.,capacitance_f=e['wired_pad_capacitance_f']);dc_load=sum(pad_dc['ground_board'])/45. if mode=='wire' else 0j
                dc=partitioned_return_solution(0.,n,dc_source,quiet_load_s=dc_load,**options)
                vd=dc['voltage'].real
                dc_values=dict(quiet_pin=float((pad_dc['ground_board']*vd[3])[0].real),
                    quiet_rail=float(vd[1]-vd[3]),host_rail=float(vd[0]-vd[2]),
                    host_to_quiet_return=float(vd[2]-vd[3]))
                if mode=='rf':del dc_values['quiet_pin']
                tones={key:[] for key in dc_values};residuals=[]
                for f,source in sorted(sources.items()):
                    pad=hs_pad_transfer(f,capacitance_f=e['wired_pad_capacitance_f']);load=sum(pad['ground_board'])/45. if mode=='wire' else 0j
                    result=partitioned_return_solution(f,n,source,quiet_load_s=load,**options)
                    v=result['voltage'];residuals.append(result)
                    values=dict(quiet_pin=pad['ground_board'][0]*v[3],quiet_rail=v[1]-v[3],
                        host_rail=v[0]-v[2],host_to_quiet_return=v[2]-v[3])
                    if mode=='rf':del values['quiet_pin']
                    for key,value in values.items():tones[key].append(dict(frequency_hz=f,
                        clock_rail_voltage_peak_v=float(abs(value)),voltage_phase_rad=float(np.angle(value))))
                envelopes={key:rail_excursion(t,dc_v=dc_values[key],samples_per_fastest_period=128 if mode=='wire' else 16) for key,t in tones.items()}
                delay=supply_delay_tones(tones['quiet_rail'],[dict(ps_per_mv=.1,pole_hz=1e9,latency_s=0.)])
                rf_observation=None
                if mode=='rf' and name in ('tied_control','lower_interreturn_capacitance','two_host_eight_quiet_site_hypothesis'):
                    supply_phase=tuple((x['frequency_hz'],-2*np.pi*carrier*x['delay_peak_s'],x['delay_phase_rad']) for x in delay['tones'])
                    phase=PhaseNoise(e['phase_components']['source']).plus(PhaseNoise(e['phase_components']['input'])).plus(PhaseNoise(supply_phase))
                    trial=dict(e,ledger=dict(ledger,local_payload_clock_core_rail_v=dc_values['quiet_rail'],
                        rf_clock_core_rail_v=dc_values['quiet_rail'],host_rail_v=dc_values['host_rail']),
                        host_spectrum=dict(h,tones=tones['quiet_rail']),supply_delay=delay,
                        delivered_phase_tones=phase.tones,
                        crossing_delay_tones=[dict(frequency_hz=f,delay_peak_s=abs(v)/(2*np.pi*carrier),
                            delay_phase_rad=p+(np.pi if v>0 else 0.)) for f,v,p in phase.tones],
                        reference_fraction_tones=[(x['frequency_hz'],
                            float(abs(x['clock_rail_voltage_peak_v']*reference_supply_transfer(e,x['frequency_hz']))),
                            float(x['voltage_phase_rad']+np.angle(reference_supply_transfer(e,x['frequency_hz'])))) for x in tones['quiet_rail']])
                    rf_observation=wideband_receive(trial,gain_settings_db=(context['resolved_configuration']['pga_gain_db'],))
                rows.append(dict(context,probe_assumptions=dict(routing_options=options,move_host_input_supply=move_input,
                    topology_scope='Explicit alternative routing fixture; not selectable hardware',
                    pad_scope='USB-like 45 ohm passive loads attached to wired fixture; not a USB operating configuration',
                    supply_sensitivity_ps_per_mv=.1),network_case=label,mode=mode,carrier_hz=carrier,variant=name,requirements=options,
                    host_input_current_owner='feed/HOST' if move_input else 'quiet local supply / HOST return',
                    total_current_a=ledger['total_chip_supply_current_a'],total_local_cap_f=n['network']['die_c'],
                    ledger=ledger,dc_nodes_v=vd.tolist(),envelopes=envelopes,
                    assigned_supply_delay_rms_ps=delay['rms_delay_s']*1e12,wideband_receive=rf_observation,
                    quiet_pin_instantaneous_guard_met=(max(abs(x) for x in envelopes['quiet_pin']['enclosed_interval_v'])<=.020 if mode=='wire' else None),
                    usb_terminations_active=(mode=='wire'),
                    kcl_residual_a=max(x['kcl_residual_a'] for x in residuals),
                    power_residual_w=max(abs(x['power_residual_w']) for x in residuals)))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        site_count_hypothesis=dict(host=host_sites,quiet=quiet_sites,host_fraction=host_share,
            qualified_isolation_or_impedance=False),
        scope='Five-node linear routing sensitivity at unchanged host rate and edge charge, with shared inventory DC allocations and reservoir capacitance. Routing and passive termination alternatives are explicit comparison fixtures, not implemented configurations or proven conservative bounds. Hypothetical existing ground groups, not a provider bond assignment. Matching tied-return control preserves original parallel return R/L. The 0.2 host share is an equal-per-site impedance hypothesis for the two north/south ground sites versus eight east/west sites, not extracted conductance or an approved isolated ring. Quiet pad terminations close into the wired network and are disabled in RF mode; host return can still enter the quiet reservoir through shared supplies. Moved input supply is a physical routing requirement, not relabeled current. Host reservoir allocation consumes existing capacitance, scaling ESR inversely with area. No mutual inductance, nonlinear substrate/ESD coupling, physical GPIO capture, RF packet/clock qualification or fabrication proof. RF comparisons propagate quiet rail to voltage, reference and supply-induced phase at resolved legal PGA gain, retaining the same external source/input noise. They use assigned-ENOB conversion; causal SAR load feedback and other benches still require the partitioned network before any architecture adoption. The external REF_IN response to moving quiet ground and its own return current are not yet included; source/input noise remains assigned. Ground differences and both rail envelopes are retained; a quiet pin alone cannot select a mitigation.')


def reference_input_solution(frequency_hz,candidate,injection,*,source_v=0j,
        cap_f=3e-12,bond_l_h=2e-9,source_r_ohm=50.2,return_options=None):
    """Clock source, series signal bond, input C and return network solved together.

    Voltage phasors use Re(V exp(jwt)). The input is an incremental high-Z
    receiver about an unspecified bias point, not an absolute pad-voltage model.
    Source return is the board reference; no ideal local ground is substituted.
    """
    if not all(math.isfinite(v) and v>0 for v in (frequency_hz,cap_f,bond_l_h,source_r_ohm)) or not np.isfinite(source_v):
        raise ValueError('Positive passive input parameters and finite source required')
    w=2*np.pi*frequency_hz;zc=1/(1j*w*cap_f);zs=source_r_ohm+1j*w*bond_l_h
    y=1/(zs+zc);drive=np.array(injection,dtype=complex,copy=True)
    if drive.shape!=(5,):raise ValueError('Five supply/return injections required')
    drive[3]+=y*source_v
    result=partitioned_return_solution(frequency_hz,candidate,drive,
        quiet_load_s=y,**(return_options or {}))
    v=result['voltage'];current=y*(source_v-v[3]);local=zc*current
    return dict(local_input_v=complex(local),input_return_current_a=complex(current),
        pad_board_v=complex(v[3]+local),network_voltage=v,
        source_real_power_w=float(np.real(source_v*np.conj(current))/2),
        kcl_residual_a=result['kcl_residual_a'],power_residual_w=result['power_residual_w'])


def reference_edge_screen(carrier_hz,carrier_v,tones,*,threshold_v=.020,substeps=32,downstream_delay_tones=(),capture=None,peak_limit_v=.6):
    """Rising threshold events over one coherent host/carrier period.

    Count every resolved rising crossing, not just the root nearest the ideal
    edge. Grid refinement is a diagnostic, not proof against all tangencies.
    No phase linearization is used to locate the reported edges.
    """
    if isinstance(peak_limit_v,bool) or not math.isfinite(peak_limit_v) or peak_limit_v<=0:
        raise ValueError('Positive finite incremental input peak limit required')
    if not math.isfinite(carrier_hz) or carrier_hz<=0 or not math.isfinite(threshold_v) or not np.isfinite(carrier_v) or abs(carrier_v)<=abs(threshold_v) or type(substeps) is not int or substeps<8:
        raise ValueError('Carrier crossing and at least eight substeps required')
    if any(not np.isfinite(v) for _,v in list(tones)+list(downstream_delay_tones)):raise ValueError('Finite voltage/delay phasors required')
    frequencies=[carrier_hz]+[f for f,_ in tones]+[f for f,_ in downstream_delay_tones]
    if any(not math.isfinite(f) or f<=0 or abs(f-round(f))>1e-6 for f in frequencies):raise ValueError('Positive integer-Hz coherent frequencies required')
    fundamental=math.gcd(*(round(f) for f in frequencies));cycles=round(carrier_hz/fundamental)
    if cycles>100000:raise ValueError('Coherent edge record exceeds fast-screen bound')
    w=2*np.pi*carrier_hz;amplitude=abs(carrier_v);phi=np.angle(carrier_v)+np.pi/2
    nominal_phase=(np.arcsin(threshold_v/amplitude)-phi)%(2*np.pi)
    nominal=(np.arange(cycles)+nominal_phase/(2*np.pi))/carrier_hz
    def value(times):
        return amplitude*np.sin(w*times+phi)-threshold_v+sum(np.real(v*np.exp(2j*np.pi*f*times)) for f,v in tones)
    grid=nominal[:,None]+np.linspace(-.5,.5,substeps+1)[None,:]/carrier_hz
    sampled=value(grid);rising=(sampled[:,:-1]<0)&(sampled[:,1:]>=0)
    counts=rising.sum(axis=1);valid=counts==1;indices=np.argmax(rising,axis=1)
    centers=nominal[valid];lo=grid[np.flatnonzero(valid),indices[valid]];hi=lo+1/(carrier_hz*substeps)
    for _ in range(34):
        mid=(lo+hi)/2;above=value(mid)>=0
        hi=np.where(above,mid,hi);lo=np.where(above,lo,mid)
    roots=(lo+hi)/2;error=roots-centers
    downstream=sum((np.real(v*np.exp(2j*np.pi*f*roots)) for f,v in downstream_delay_tones),np.zeros_like(roots))
    combined=error+downstream
    spacing=np.diff(np.r_[roots+downstream,roots[0]+downstream[0]+cycles/carrier_hz]) if np.all(valid) else None
    if capture is not None:
        capture.update(period_s=1/fundamental,nominal_edges_s=centers.copy(),input_edges_s=roots.copy(),
            output_edges_s=(roots+downstream).copy(),complete=bool(np.all(valid) and np.all(spacing>0)))
    slope=w*np.sqrt(amplitude**2-threshold_v**2)
    linear=-sum(np.real(v*np.exp(2j*np.pi*f*centers)) for f,v in tones)/slope
    if not tones:linear=np.zeros_like(centers)
    rms=float(np.std(error)) if len(error) else None
    peak_to_peak=float(np.ptp(error)) if len(error) else None
    dominant=[]
    if np.all(valid):
        coefficients=np.fft.rfft(error-error.mean())/len(error)
        for k in sorted(range(1,len(coefficients)),key=lambda j:abs(coefficients[j]),reverse=True)[:8]:
            factor=1 if len(error)%2==0 and k==len(error)//2 else 2
            dominant.append(dict(frequency_hz=k*fundamental,edge_error_peak_ps=float(factor*abs(coefficients[k])*1e12)))
    return dict(carrier_cycles=cycles,period_s=1/fundamental,grid_substeps=substeps,
        missing_rising_edge_windows=int(sum(counts==0)),multiple_rising_edge_windows=int(sum(counts>1)),
        unique_edge_windows=int(sum(valid)),all_windows_have_one_rising_edge=bool(np.all(valid)),
        centered_edge_error_rms_ps=None if rms is None else rms*1e12,
        edge_error_peak_to_peak_ps=None if peak_to_peak is None else peak_to_peak*1e12,
        static_mean_edge_shift_ps=None if not len(error) else float(np.mean(error)*1e12),
        maximum_root_voltage_residual_v=None if not len(error) else float(max(abs(value(roots)))),
        linearization_maximum_error_ps=None if not len(error) else float(max(abs(error-linear))*1e12),
        dominant_edge_error_tones=dominant,
        combined_edge_error_rms_ps=None if not len(error) else float(np.std(combined)*1e12),
        combined_edge_error_peak_to_peak_ps=None if not len(error) else float(np.ptp(combined)*1e12),
        downstream_delay_rms_at_edges_ps=None if not len(error) else float(np.std(downstream)*1e12),
        minimum_output_edge_spacing_s=None if spacing is None else float(min(spacing)),
        output_clock_order_preserved=None if spacing is None else bool(np.all(spacing>0)),
        local_input_conservative_peak_v=float(amplitude+sum(abs(v) for _,v in tones)),
        incremental_envelope_met=bool(amplitude+sum(abs(v) for _,v in tones)<=peak_limit_v),
        threshold_v=threshold_v,peak_limit_v=peak_limit_v)


def reference_return_campaign(contract,*,design=None):
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[]
    sites=contract['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
    host_count=sum('vss_pads[' in site for side in ('north','south') for site in sites[side])
    total_count=sum('vss_pads[' in site for sites_on_side in sites.values() for site in sites_on_side)
    variants=(('tied_baseline',dict(link_r_ohm=1e-5),False),
        ('split_equal_low_coupling',dict(host_cap_fraction=.5,coupling_f=2e-12),True),
        ('split_site_weighted_low_coupling',dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=host_count/total_count),True))
    for mode,carrier,word in (('wire',2.5e9,312.5e6),('rf',2.4e9,2.4e9/16),('rf',2.484e9,2.484e9/16)):
        for label,return_l,die_esl in network_cases(design):
            scenario=Scenario().override(reason='Reference-return package comparison',
                package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
            e,context=clock_screen_environment(design,mode,carrier,scenario=scenario)
            for name,options,move_input in variants:
                wanted=reference_input_solution(carrier,e['network'],np.zeros(5),source_v=.5,return_options=options)
                tones=[];delays=[];residuals=[]
                for f,injection in partitioned_host_sources(e,move_input).items():
                    result=reference_input_solution(f,e['network'],injection,return_options=options)
                    tones.append((f,result['local_input_v']));residuals.append(result)
                    quiet_rail=result['network_voltage'][1]-result['network_voltage'][3]
                    delays.append((f,quiet_rail*.1e-9/(1+1j*f/1e9)))
                carrier_delay=(wanted['network_voltage'][1]-wanted['network_voltage'][3])*.1e-9/(1+1j*carrier/1e9)
                delays.append((carrier,carrier_delay))
                edge=reference_edge_screen(carrier,wanted['local_input_v'],tones,downstream_delay_tones=delays)
                refined=reference_edge_screen(carrier,wanted['local_input_v'],tones,substeps=64,downstream_delay_tones=delays)
                source_only=reference_edge_screen(carrier,wanted['local_input_v'],[],downstream_delay_tones=[(carrier,carrier_delay)])
                rows.append(dict(context,probe_assumptions=dict(source_peak_v=.5,
                    input_topology='Single-ended comparison fixture replacing selected differential receiver',
                    downstream_sensitivity_ps_per_mv=.1,downstream_pole_hz=1e9,
                    return_topology='Explicit routing alternative; not a selectable hardware configuration'),network_case=label,mode=mode,carrier_hz=carrier,variant=name,
                    return_options=options,host_input_supply_at_feed=move_input,
                    total_reserved_current_a=e['inventory_current_report']['total_ma']/1000,
                    receiver_carrier_peak_v=float(abs(wanted['local_input_v'])),
                    receiver_carrier_phase_rad=float(np.angle(wanted['local_input_v'])),
                    carrier_input_return_peak_a=float(abs(wanted['input_return_current_a'])),
                    carrier_quiet_ground_peak_v=float(abs(wanted['network_voltage'][3])),
                    carrier_quiet_supply_peak_v=float(abs(wanted['network_voltage'][1]-wanted['network_voltage'][3])),
                    external_source_real_power_w=wanted['source_real_power_w'],
                    host_input_voltage_tones=[dict(frequency_hz=f,peak_v=float(abs(v)),phase_rad=float(np.angle(v))) for f,v in tones],
                    crossings=edge,refined_crossings=refined,source_only=source_only,
                    edge_counts_stable_on_refinement=all(edge[k]==refined[k] for k in ('missing_rising_edge_windows','multiple_rising_edge_windows')),
                    kcl_residual_a=max(x['kcl_residual_a'] for x in residuals+[wanted]),
                    power_residual_w=max(abs(x['power_residual_w']) for x in residuals+[wanted])))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Coupled passive single-ended REF_IN: 0.5 V peak Thevenin source, 50.2 ohms, 2 nH signal bond, 3 pF input, 20 mV incremental threshold. Both source carrier return and host-induced local input voltage are solved in the same PDN. Assigned 0.1 ps/mV, 1 GHz-pole downstream supply delay is evaluated at the actual input crossings, including the returned carrier; combined timing retains correlation rather than adding RMS values. Current inventory allocations are reported for context; this linear single-ended comparison does not establish DC operating headroom; no USB test terminations are active. One coherent nominal-rate period, rising edges resolved at 32 and 64 samples/UI with bracketed roots. Source-only controls remove host tones without changing loading. No receiver bias/common-mode or protection model, source AM/noise, additive receiver noise, qualified threshold/supply sensitivity, autonomous PLL, fractional host-rate/phase corners or RF/serial payload propagation. This is an explicit single-ended sensitivity control, not the selected differential reference-input path.')


def partitioned_dc_ledger(environment,options,move_input=False):
    """DC balance shared by selected differential and historical input controls."""
    e=environment;n=e['network']
    if 'design_provenance' in e and 'board_source_v' not in e:
        raise ValueError('Design-bound DC network missing board source voltage')
    source_v=e.get('board_source_v',3.3)
    ledger=selected_dc_ledger(e['payload_engine'],n,source_v=source_v,h2d_internal_a=0. if move_input else e['host_spectrum']['chip_h2d_internal_mean_a'],
                              owner_current_a=e.get('inventory_current_a'))
    internal=ledger['h2d_internal_current_within_host_a'];host=ledger['host_node_current_a']
    host_total=ledger['owner_current_a']['host']
    quiet=ledger['total_chip_supply_current_a']-host_total
    source=[source_v/n['network']['feed_r']-host,-ledger['local_branch_current_a'],host_total,quiet,0.]
    vd=partitioned_return_solution(0.,n,source,**options)['voltage'].real
    rr=n['return_r_ohm'];common=options.get('common_fraction',.1);share=options.get('host_return_share',.5)
    loss=(source_v-vd[0])**2/n['network']['feed_r']+(vd[0]-vd[1])**2/n['network']['package_r']
    loss+=(vd[2]-vd[4])**2*share/((1-common)*rr)+(vd[3]-vd[4])**2*(1-share)/((1-common)*rr)+vd[4]**2/(common*rr)
    if options.get('link_r_ohm') is not None:loss+=(vd[2]-vd[3])**2/options['link_r_ohm']
    power=host*(vd[0]-vd[2])+internal*(vd[1]-vd[2])+quiet*(vd[1]-vd[3])
    ledger=dict(ledger,board_supply_v=float(vd[0]),die_return_v=float(vd[3]),
        local_payload_clock_core_rail_v=float(vd[1]-vd[3]),rf_clock_core_rail_v=float(vd[1]-vd[3]),
        host_rail_v=float(vd[0]-vd[2]),delivered_electrical_power_w=float(power),resistive_loss_w=float(loss),
        power_balance_residual_w=float(ledger['source_power_w']-power-loss))
    return ledger


def reference_payload_environment(environment,options,move_input,*,supply_sign=1.,source_peak_v=None,sensitivity_ps_per_mv=None):
    """Selected differential frontend; explicit single-ended helper retains controls."""
    if move_input or options != dict(link_r_ohm=1e-5):
        raise ValueError('Selected differential input requires the common-return baseline')
    if environment.get('clock_domains',{}).get('synthesis_required'):
        raise ValueError('Forwarded synthesis requires retained lane-clock composition; input reference is not the line clock')
    from reference_input_probe import paired_environment
    if 'internal_switching_loads' not in environment:
        environment=dict(environment,internal_switching_loads=[
            dict(owner='timing',mean_a=.010,event_hz=environment['carrier_hz']/16,tau_s=.2e-9,harmonics=64),
            dict(owner='core',mean_a=.020,event_hz=156.25e6,tau_s=.2e-9,harmonics=64)])
    ledger=partitioned_dc_ledger(environment,options)
    config=environment['clock_input_configuration']
    if config['topology']!='differential':raise ValueError('Selected input must be differential')
    opts=dict(config['input_model'])
    if source_peak_v is None:source_peak_v=config['source_differential_peak_v']
    if sensitivity_ps_per_mv is None:sensitivity_ps_per_mv=config['supply_sensitivity_ps_per_mv']
    trial,row=paired_environment(environment,opts,sign=supply_sign,
        sensitivity_ps_per_mv=sensitivity_ps_per_mv,ledger=ledger,source_peak_v=source_peak_v)
    report=dict(row,frontend='differential',internal_switching_loads=environment['internal_switching_loads'],ledger=ledger,resolved_crossings=row['clock'],
        physical_source_peak_v=source_peak_v,supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        supply_sensitivity_sign=supply_sign,status='clock_accepted_for_conditional_payload' if trial is not None else 'clock_not_accepted_for_payload')
    return trial,report


def single_ended_reference_payload_environment(environment,options,move_input,*,supply_sign=1.,source_peak_v=.5,sensitivity_ps_per_mv=.1):
    """RF or wired environment rebuilt from the same clock-input/return solution.

    Random/AM phase allocations are overlaid after deterministic event solving;
    their interaction with threshold crossings remains a small-perturbation
    hypothesis. The old host-induced supply phase is replaced, not counted twice.
    """
    from oscillator_noise import loaded_clock_input_phase
    e=environment;n=e['network'];carrier=e['carrier_hz']
    acceptance=reference_acceptance_parameters(e)
    edge_options=dict(threshold_v=acceptance['threshold_v'],peak_limit_v=acceptance['effective_peak_limit_v'])
    delay_gain=supply_delay_gain(sensitivity_ps_per_mv,supply_sign)
    if not math.isfinite(source_peak_v) or source_peak_v<=0:raise ValueError('Positive finite external source peak required')
    ledger=partitioned_dc_ledger(e,options,move_input)
    wanted=reference_input_solution(carrier,n,np.zeros(5),source_v=source_peak_v,return_options=options)
    input_tones=[];delays=[];rails=[]
    def rail_tone(f,v):return dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v)))
    for f,injection in partitioned_host_sources(e,move_input).items():
        r=reference_input_solution(f,n,injection,return_options=options)
        input_tones.append((f,r['local_input_v']))
        v=r['network_voltage'][1]-r['network_voltage'][3]
        rails.append(rail_tone(f,v));delays.append((f,delay_gain*v/(1+1j*f/clock_supply_delay_pole(e))))
    v=wanted['network_voltage'][1]-wanted['network_voltage'][3]
    rails.append(rail_tone(carrier,v));delays.append((carrier,delay_gain*v/(1+1j*carrier/clock_supply_delay_pole(e))))
    capture={}
    coarse=reference_edge_screen(carrier,wanted['local_input_v'],input_tones,**edge_options,downstream_delay_tones=delays)
    resolved=reference_edge_screen(carrier,wanted['local_input_v'],input_tones,**edge_options,downstream_delay_tones=delays,substeps=64,capture=capture)
    stable=all(coarse[k]==resolved[k] for k in ('missing_rising_edge_windows','multiple_rising_edge_windows'))
    report=dict(supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,supply_sensitivity_sign=supply_sign,coarse_crossings=coarse,resolved_crossings=resolved,
        payload_engine=e['payload_engine'],
        physical_source_peak_v=source_peak_v,
        source_carrier_return_peak_a=float(abs(wanted['input_return_current_a'])),
        source_carrier_real_power_w=wanted['source_real_power_w'],
        edge_counts_stable=stable,ledger=ledger,return_options=options,
        receiver_carrier_peak_v=float(abs(wanted['local_input_v'])))
    if not capture['complete'] or not stable or not resolved['incremental_envelope_met']:
        return None,dict(report,status='clock_not_accepted_for_payload',
            reason='Incomplete/unordered/unresolved edges or outside the assigned incremental input-voltage bound; no repaired clock substituted.')
    old_peak=e['external_clock_input']['receiver_peak_v']
    gain_equivalent_source=e['external_clock_input']['source_peak_v']*abs(wanted['local_input_v'])/old_peak
    input_phase,input_report=loaded_clock_input_phase(carrier,
        receiver_noise_v=e['external_clock_input']['receiver_noise_v'],
        downstream_stage_rms_s=e['external_clock_input']['downstream_stage_rms_s'],
        source_peak_v=gain_equivalent_source,**edge_options)
    phase=tuple(e['phase_components']['source'])+tuple(input_phase.tones)
    record=dict(carrier_hz=carrier,period_s=capture['period_s'],edges_s=capture['output_edges_s'])
    reference=[]
    for t in rails:
        h=reference_supply_transfer(e,t['frequency_hz'])
        reference.append((t['frequency_hz'],float(t['clock_rail_voltage_peak_v']*abs(h)),float(t['voltage_phase_rad']+np.angle(h))))
    trial=dict(e,ledger=ledger,host_spectrum=dict(e['host_spectrum'],tones=rails),
        reference_return_options=dict(options),local_supply_delay_sign=supply_sign,local_supply_sensitivity_ps_per_mv=sensitivity_ps_per_mv,
        reference_threshold=dict(carrier_v=wanted['local_input_v'],input_tones=input_tones,
            downstream_delay_tones=delays,threshold_v=acceptance['threshold_v'],input_edges_s=capture['input_edges_s'],period_s=capture['period_s']),
        rail_maximum_offset_hz=max(t['frequency_hz'] for t in rails),
        reference_fraction_tones=reference,periodic_clock=record,delivered_phase_tones=phase,
        crossing_delay_tones=[],phase_components=dict(source=e['phase_components']['source'],input=input_phase.tones,supply=()),
        external_clock_input=dict(input_report,physical_source_peak_v=source_peak_v,
            source_peak_interpretation='Gain-equivalent ideal-ground parameter only; physical amplitude is physical_source_peak_v.'))
    report.update(status='clock_accepted_for_conditional_payload',
        edge_record=dict(count=len(record['edges_s']),period_s=record['period_s'],
            first_edge_s=float(record['edges_s'][0]),sha256=hashlib.sha256(record['edges_s'].astype('<f8').tobytes()).hexdigest()),
        input_noise_reference=trial['external_clock_input'],
        source_and_input_phase_tone_count=len(phase),
        rail_tones_include_external_clock_carrier=True)
    return trial,report


def coupled_wideband_feedback(environment,*,wanted_dbm=-65.,gain_db=None,oversample=None,
                              filter_integrator_ratio=None,filter_retune_ratio=None,
                              sar_parameters=None,comparator_model=None,gain_codes_db=None,
                              blocker_dbm=-30.,noise_figure_db=None,input_iip3_dbm=None,
                              gain_initial_db=None,gain_tau_s=None,gain_command_s=0.,gain_hypothesis_reason=None):
    """Causal SAR/input/rail loop; fixed gain, no oracle gain selection."""
    config=environment.get('resolved_configuration')
    if config is not None:
        if config['engine']!='rf' or config['direction']!='rx':
            raise ValueError('RF receive configuration required')
        if gain_db is not None and gain_db!=config['pga_gain_db']:
            raise ValueError('Gain override conflicts with resolved hardware configuration')
        gain_db=config['pga_gain_db']
        inventory=receiver_inventory_options(environment)
        if gain_codes_db is not None and tuple(gain_codes_db)!=inventory['gain_codes_db']:
            raise ValueError('Gain code override conflicts with design snapshot')
        gain_codes_db=inventory['gain_codes_db']
        if noise_figure_db is None:noise_figure_db=inventory['noise_figure_db']
        if input_iip3_dbm is None:input_iip3_dbm=inventory['input_iip3_dbm']
    elif gain_db is None:
        gain_db=receiver_inventory_options(environment)['maximum_gain_db']
    if noise_figure_db is None:noise_figure_db=6.
    if input_iip3_dbm is None:input_iip3_dbm=0.
    if oversample is None:oversample=max(256,minimum_envelope_oversample(environment))
    if environment.get('reference_return_options')!={'link_r_ohm':1e-5} or environment.get('payload_engine')!='rf':
        raise ValueError('Coupled SAR feedback requires the selected tied-return RF topology')
    response=None;iterations=[];converged=False
    for iteration in range(4):
        capture={}
        converter_rx=wideband_receive(environment if response is None else dict(environment,local_load_response=response),
            oversample=oversample,wanted_dbm=wanted_dbm,gain_settings_db=(gain_db,),
            gain_hypothesis_reason=gain_hypothesis_reason,
            sar_parameters=environment_converter_parameters(environment) if sar_parameters is None else sar_parameters,load_capture=capture,
            comparator_model=comparator_model,gain_codes_db=gain_codes_db,
            blocker_dbm=blocker_dbm,noise_figure_db=noise_figure_db,input_iip3_dbm=input_iip3_dbm,
            gain_initial_db=gain_initial_db,gain_tau_s=gain_tau_s,gain_command_s=gain_command_s,
            filter_integrator_ratio=filter_integrator_ratio,filter_retune_ratio=filter_retune_ratio)
        updated,load=reference_feedback_response(capture,environment)
        rms,peak,rail_converged=response_change(updated,response)
        input_peak=None
        if response is not None:
            mask=(updated['times_s']>=response['times_s'][0])&(updated['times_s']<=response['times_s'][-1])
            input_peak=float(max(abs(updated['input_v'][mask]-np.interp(updated['times_s'][mask],response['times_s'],response['input_v']))))
        converged=rail_converged and input_peak is not None and input_peak<=1e-6
        iterations.append(dict(iteration=iteration,rail_rms_change_v=rms,rail_peak_change_v=peak,
            input_voltage_peak_change_v=input_peak,clock=converter_rx['coupled_load_clock'],load=load))
        response=updated
        if converged:break
    load_controls=[]
    for grid in (.25e-9,.125e-9):
        _,load=reference_feedback_response(capture,environment,grid_s=grid)
        load_controls.append(load)
    return dict(design_provenance=deepcopy(environment.get('design_provenance')),
        resolved_configuration=deepcopy(environment.get('resolved_configuration')),
        scenario_overrides=deepcopy(environment.get('scenario_overrides',[])),
        scenario_assumptions=deepcopy(environment.get('scenario_assumptions',{})),
        operating_conditions=deepcopy(environment.get('operating_conditions')),
        receiver=converter_rx,load_resolution=load_controls,
        iterations=iterations,feedback_closed=True,numerical_feedback_converged=converged,
        scope='Causal SAR recharge drives the tied-return PDN including REF_IN loading. Perturbed local threshold roots and reevaluated downstream supply delay drive the next pass. Numerical guards: 1 uV RMS / 20 uV peak rail change and 1 uV peak input change. Extra crossings outside local root brackets, real acquisition and physical devices remain unqualified.')


def reference_payload_campaign(contract,*,design=None):
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[]
    sites=contract['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
    share=sum('vss_pads[' in x for side in ('north','south') for x in sites[side])/sum('vss_pads[' in x for group in sites.values() for x in group)
    for label,return_l,die_esl in network_cases(design):
        variants=[('tied_baseline',dict(link_r_ohm=1e-5),False)]
        if label==BASELINE_PACKAGE_CASE:
            variants += [('split_equal_low_coupling',dict(host_cap_fraction=.5,coupling_f=2e-12),True),
                         ('split_site_weighted_low_coupling',dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=share),True)]
        for carrier in (2.4e9,2.484e9):
            scenario=Scenario().override(reason='Reference payload package comparison',
                package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
            e,context=clock_screen_environment(design,'rf',carrier,scenario=scenario)
            gain=context['resolved_configuration']['pga_gain_db']
            tx_config=design.configure(engine='rf',direction='tx',reference_hz=carrier,sample_divider=64)
            tx_seed=configured_environment(tx_config,scenario)
            for name,options,move_input in variants:
                for sign in (1.,-1.):
                    factory=reference_payload_environment if name=='tied_baseline' else single_ended_reference_payload_environment
                    trial,clock=factory(e,options,move_input,supply_sign=sign)
                    tx_trial,tx_clock=factory(tx_seed,options,move_input,supply_sign=sign)
                    rx=tx=None;resolution=[];legacy=None;swing_controls=[];converter_port=None;weak_converter=None
                    if name=='tied_baseline' and sign==1.:
                        for swing in (.75,1.):
                            swing_trial,swing_clock=single_ended_reference_payload_environment(e,options,move_input,
                                supply_sign=sign,source_peak_v=swing)
                            swing_controls.append(dict(clock=swing_clock,receiver=None if swing_trial is None else
                                wideband_receive(swing_trial,oversample=max(256,minimum_envelope_oversample(swing_trial)),gain_settings_db=(gain,)),
                                scope='Source amplitude changes return current, rail carrier, crossing events and input noise together. Assigned positive supply sensitivity only; RX diagnostic, not TX/acquisition or physical input qualification.'))
                    if trial is not None:
                        if name=='tied_baseline':
                            weak_converter=coupled_wideband_feedback(trial,wanted_dbm=-85.,gain_db=gain)
                        if name=='tied_baseline' and sign==1. and carrier==2.484e9:
                            converter_port=coupled_wideband_feedback(trial)
                        if name=='tied_baseline' and sign==1.:
                            legacy=dict(receiver=wideband_receive(e,oversample=max(256,minimum_envelope_oversample(e)),gain_settings_db=(gain,)),
                                transmitter=wideband_transmit(tx_seed,oversample=max(256,minimum_envelope_oversample(tx_seed))))
                        rx=wideband_receive(trial,oversample=max(256,minimum_envelope_oversample(trial)),gain_settings_db=(gain,))
                        if label==BASELINE_PACKAGE_CASE and name=='tied_baseline' and sign==1.:
                            for oversample in (max(256,minimum_envelope_oversample(trial)),2*max(256,minimum_envelope_oversample(trial))):
                                from selected_rf import he_observation
                                clean_capture={};blocked_capture={}
                                clean=wideband_receive(trial,oversample=oversample,noise=False,gain_settings_db=(gain,),
                                    blocker_dbm=None,observation_capture=clean_capture)
                                blocked=wideband_receive(trial,oversample=oversample,noise=False,gain_settings_db=(gain,),
                                    observation_capture=blocked_capture)
                                clean_training=he_observation(blocked_capture['wave'],blocked_capture['observed'],
                                    diagnostic_training=clean_capture['observed'])
                                resolution.append(dict(oversample=oversample,
                                    receiver=blocked,receiver_without_blocker=clean,
                                    blocked_with_clean_training_diagnostic=clean_training,
                                    receiver_linear_forcing=wideband_receive(trial,oversample=oversample,noise=False,gain_settings_db=(gain,),filter_interpolation='linear'),
                                    transmitter=None if tx_trial is None else wideband_transmit(tx_trial,oversample=oversample,noise=False)))
                    if tx_trial is not None:
                        tx=wideband_transmit(tx_trial,oversample=max(256,minimum_envelope_oversample(tx_trial)))
                    rows.append(dict(context,network_case=label,carrier_hz=carrier,variant=name,
                        transmit_configuration=tx_config.record(),transmit_clock=tx_clock,
                        diagnostic_topology=dict(options=options,move_input=move_input,
                            single_ended=name!='tied_baseline',supply_sensitivity_sign=sign),
                        clock=clock,receiver=rx,transmitter=tx,previous_environment_control=legacy,resolution_controls=resolution,
                        source_swing_controls=swing_controls,converter_load_port_control=converter_port,
                        weak_converter_feedback=weak_converter))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='RX and TX are independently configured from the same design and package scenario; this is not a continuous turnaround simulation. PGA uses the legal resolved gain. Split-return and source-swing single-ended controls are counterfactual clock-input fixtures, not hardware configurations. Corrected deterministic REF_IN edges and correlated supply delay now drive RF LO phase and ADC/DAC event timing. Both supply-sensitivity signs are tested. A same-grid previous-environment control separates migration from a mere envelope-sampling change; it is not a single-impairment intervention. Same coupled network drives rail/headroom and reference modulation, including returned source carrier. The baseline covers every package; split hypotheses are compared at the current package target. Source/AM/input phase allocations are retained and gain-normalized to loaded carrier amplitude as small perturbations, not solved jointly at the analog threshold. Rising-edge interpolation does not qualify duty cycle, quadrature or regenerated waveform harmonics; Noiseless 256/512 envelope-grid controls, plus 1024 at 2.4 GHz, test numerical sensitivity; the 2.4 GHz RX EVM is not yet converged. Invalid edge records are rejected before payload simulation. Main sweep uses assigned-ENOB ADC/DAC and known DATA training. Tied positive-sensitivity 2.484 GHz cases additionally close causal SAR recharge through loaded REF_IN and threshold events at moderate wanted power. Tied-return weak-signal causal feedback covers both RF endpoints and sensitivity signs. Driver wake and wired consumers have separate joined campaigns; real wideband preamble/packets and physical devices remain unqualified.')


def diagnostic_input_environment(design,carrier,scenario,settings):
    """Explicit input-model intervention; not a legal hardware setting."""
    config=design.configure(engine='rf',direction='rx',reference_hz=carrier,sample_divider=64,
        pga_gain_db=max(design.architecture['blocks']['pga_i']['parameters']['gain_db']))
    allowed={'threshold_v','am_depth','source_peak_v','receiver_noise_v','downstream_stage_rms_s','noise_bins','seed'}
    if set(settings)-allowed:raise ValueError('Unknown clock-input diagnostic intervention')
    environment=inventory_environment(design.contract,design.architecture,'rf',carrier,config.host_word_hz,
        design=design,external_input=settings,diagnostic_input_reason='Explicit clock-input contribution isolation',
        **scenario.electrical_options(design))
    environment['diagnostic_input_intervention']=dict(settings)
    return _bind_configured_environment(config,scenario,environment)


def wideband_diagnosis(contract,*,design=None):
    """Paired interventions, never mixed into a claimed implementation pass."""
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    rows=[]
    for label,return_l,die_esl in network_cases(design):
        for carrier in (2.4e9,2.484e9):
            scenario=Scenario().override(reason='Wideband diagnostic package comparison',
                package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
            e,context=clock_screen_environment(design,'rf',carrier,scenario=scenario)
            cases=[]
            recipes=[('all_effects',{},()),('thermal_off',dict(disabled_noise_sources=('thermal',)),()),
                ('converter_noise_off',dict(disabled_noise_sources=('converter',)),()),
                ('aperture_off',dict(disabled_noise_sources=('aperture',)),()),
                ('blocker_off',dict(blocker_dbm=None),()),('assigned_9enob',dict(adc_enob=9.,
                    diagnostic_reason='Isolate receiver sensitivity to assigned converter precision'),()),
                ('source_phase_off',{},('source',)),('input_phase_off',{},('input',)),
                ('input_am_off',{},('input_am',)),('input_noise_off',{},('input_noise',)),
                ('supply_phase_off',{},('supply',)),('all_phase_off',{},('source','input','supply'))]
            for name,options,removed in recipes:
                current=e
                if removed:
                    components=dict(e['phase_components'])
                    if 'input_am' in removed:components['input']=e['external_clock_input']['phase_components']['additive']
                    if 'input_noise' in removed:components['input']=e['external_clock_input']['phase_components']['am']
                    phase=tuple(t for key,tones in components.items() if key not in removed for t in tones)
                    current=dict(e,delivered_phase_tones=phase,
                        crossing_delay_tones=[dict(frequency_hz=f,delay_peak_s=abs(a)/(2*math.pi*carrier),
                            delay_phase_rad=p+(math.pi if a>0 else 0.)) for f,a,p in phase])
                rx=wideband_receive(current,**options)
                cases.append(dict(diagnostic_options=options,intervention=name,removed_phase_components=list(removed),receiver=rx))
            for name,settings in (('threshold_centered',dict(threshold_v=.002)),
                                  ('lower_source_am',dict(am_depth=.01)),
                                  ('larger_clock_swing',dict(source_peak_v=.75)),
                                  ('quieter_input_distribution',dict(receiver_noise_v=25e-6,downstream_stage_rms_s=5e-15))):
                current=diagnostic_input_environment(design,carrier,scenario,settings)
                cases.append(dict(diagnostic_options=settings,intervention=name,external_input=current['external_clock_input'],
                    receiver=wideband_receive(current)))
            refinement=[]
            if label==BASELINE_PACKAGE_CASE:
                for bins,seed in ((128,1831),(512,1831),(512,1841)):
                    current=diagnostic_input_environment(design,carrier,scenario,dict(noise_bins=bins,seed=seed))
                    refinement.append(dict(input_noise_bins=bins,input_noise_seed=seed,
                        external_input=current['external_clock_input'],
                        receiver=wideband_receive(current,gain_settings_db=(context['resolved_configuration']['pga_gain_db'],))))
            rows.append(dict(context,network_case=label,carrier_hz=carrier,cases=cases,input_noise_refinement=refinement))
    return dict(design_provenance=design.provenance(),cases=rows,complete=False,
        scope='Same weak wanted signal, blocker, waveform/noise seeds, package and mode budget. One-effect interventions identify causal requirements; disabled noise, altered clock-input requirements and higher assigned ENOB are diagnostic, not free circuit upgrades. Gain uses the resolved setting; interventions are model counterfactuals, not circuit specifications or selectable controls. Known DATA training, finite phase lines and uncoded BPSK errors do not establish Wi-Fi packet sensitivity or compliance.')


def baseline_source_hashes():
    """Declared baseline dependencies; sampled before and after a full run."""
    sources=['verification/baseline_envelope.py','verification/robustness_envelope.py',
             'system_model/architecture_fast/design_definition.py',
             'system_model/architecture_fast/video_alignment.py',
             'system_model/architecture_fast/rf_quality_budget.py',
             'system_model/connected/oscillator_noise.py','verification/wired_envelope.py',
             'verification/selected_rf.py','verification/ble_packet.py',
             'verification/converter_dynamics.py','verification/reference_input_probe.py','system_model/connected/protocol_pad.py',
             'verification/check_contract.py','system_model/architecture_fast/resource_configuration.py',
             'system_model/connected/protocol_signals.py','system_model/connected/tx_output_stage.py',
             'system_model/connected/tx_output_candidate.py',
             'system_model/connected/wired_blocks.py','system_model/architecture_fast/behavioral.py','spec/contract.json',
             'spec/block-diagram.md','spec/power-partition.md','spec/analog-architecture.json']
    # Transitive project imports observed in the package-validation runner.
    sources += [
        'system_model/connected/autonomous_pll.py',
        'system_model/connected/charge_pump_filter.py',
        'system_model/connected/compliant_edge_pll.py',
        'system_model/connected/compliant_pump_filter.py',
        'system_model/connected/edge_pump_pll.py',
        'system_model/connected/fractional_pulse_pll.py',
        'system_model/connected/lane_group.py',
        'system_model/connected/reference_sample_clock.py',
        'system_model/connected/sampled_pll.py',
        'system_model/connected/shaped_fractional_pll.py',
        'system_model/connected/tx_dac_correction.py',
        'system_model/connected/tx_iq_calibration.py',
        'verification/block_receiver_model.py',
        'verification/stream_codec.py',
        'verification/transport_model.py',
    ]
    # Optional-branch transitive imports from the static dependency review.
    sources += [
        'system_model/architecture_fast/direct_stream.py',
        'system_model/architecture_fast/receive_qualification.py',
        'system_model/architecture_fast/rf_air_timing.py',
        'system_model/connected/bit_event_stream.py',
        'system_model/connected/burst_codec.py',
        'system_model/connected/chip_model.py',
        'system_model/connected/fractional_pulse_screen.py',
        'system_model/connected/loopback_return.py',
        'verification/bit_event_codec.py',
        'verification/recovery_mailbox.py',
        'verification/rf_gain_command.py',
        'verification/rf_power_calibration.py',
        'verification/rf_timing_command.py',
        'verification/selected_lifecycle.py',
        'verification/selected_revision_check.py',
        'verification/usb_selected_timing.py',
        'verification/wired_lock_probe.py',
        'verification/wideband_packet.py',
        'verification/wifi_client_exchange.py',
        'verification/external_wifi_reference.py',
        'verification/he64_packet.py',
        'verification/rf_filter_tradeoff.py',
        'system_model/architecture_fast/timing_services.py',
    ]
    return {name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in sources}


def run():
    before=baseline_source_hashes()
    design=load_design();contract=design.contract
    from concurrent.futures import ThreadPoolExecutor
    # Independent, read-only benches use local RNG/state. Wait for all before
    # snapshotting provenance; only the main thread writes the evidence file.
    with ThreadPoolExecutor(max_workers=3) as workers:
        packets=workers.submit(narrowband_exchange,contract,design=design)
        converters=workers.submit(converter_feedback,contract,design=design)
        diagnosis=workers.submit(wideband_diagnosis,contract,design=design)
        result=assemble_baseline(contract,packets,converters,diagnosis,design=design)
    if baseline_source_hashes()!=before:
        raise RuntimeError('Sources changed during baseline campaign')
    result['sources_sha256']=before
    result['source_verification']='Declared baseline dependencies unchanged across the full campaign'
    return result


def assemble_baseline(contract,packets,converters,diagnosis,*,design=None):
    from design_definition import Scenario
    design=design_for_contract(contract,design)
    # Resolve and validate supplied campaign results before any new simulation.
    # Each campaign may contain explicitly labeled circuit variants, but its
    # root must identify the shared snapshot from which those variants started.
    inputs={name:future.result() for name,future in (
        ('narrowband_rf',packets),('converter_reference_feedback',converters),
        ('wideband_diagnosis',diagnosis))}
    for name,capture in inputs.items():
        if not isinstance(capture,dict) or capture.get('design_provenance')!=design.provenance():
            raise ValueError(name+' baseline input does not match shared design')
    rows=[];wired_scenarios=[];wired_inputs=[];rf_rows=[];rf_controls=[]
    for mode,carrier,word in (('rf',2.4e9,2.4e9/16),('rf',2.484e9,2.484e9/16),
                              ('wire',2.5e9,312.5e6)):
        for label,return_l,die_esl in network_cases(design):
            scenario=Scenario().override(reason='Baseline assembly package comparison',
                package_return_inductance_h=return_l,die_decoupling_esl_h=die_esl)
            e,context=clock_screen_environment(design,mode,carrier,scenario=scenario)
            if mode=='rf':
                tx_config=design.configure(engine='rf',direction='tx',reference_hz=carrier,sample_divider=64)
                tx_environment=configured_environment(tx_config,scenario)
            candidate=e['network']
            tone_bound=sum(t['clock_rail_voltage_peak_v'] for t in e['host_spectrum']['tones'])
            rail=e['ledger']['local_payload_clock_core_rail_v']
            supply_shift=math.sqrt(sum(t['delay_peak_s']**2/2 for t in e['supply_delay']['tones']))
            corners=[]
            for voltage in (3.267,3.3,3.333):
                dc=selected_dc_ledger(mode,candidate,source_v=voltage,owner_current_a=e['inventory_current_a'],h2d_internal_a=e['host_spectrum']['chip_h2d_internal_mean_a'])
                corners.append(dict(board_source_v=voltage,ledger=dc,
                    nominal_spectrum_rail_lower_bound_v=dc['local_payload_clock_core_rail_v']-tone_bound,
                    nominal_spectrum_rail_upper_bound_v=dc['local_payload_clock_core_rail_v']+tone_bound))
            if mode=='wire':
                wired_input=baseline_wired_receiver_inputs(e,label=label)
                wired_inputs.append(dict(context,**wired_input))
                wired_scenarios.append(wired_input['timing_scenario'])
            else:
                rf_rows.append(dict(context,tx_resolved_configuration=tx_config.record(),carrier_hz=carrier,network_case=label,
                    receiver=[wideband_receive(e,wanted_dbm=level) for level in (-65.,-85.)],
                    transmitter=wideband_transmit(tx_environment)))
                if carrier==2.4e9:
                    rf_controls.append(dict(context,tx_resolved_configuration=tx_config.record(),carrier_hz=carrier,network_case=label,
                        rx_all_pole_control=wideband_receive(e,family='rx_all_pole_control'),
                        resolution=[dict(oversample=n,
                            receiver=wideband_receive(e,oversample=n,noise=False,gain_settings_db=(context['resolved_configuration']['pga_gain_db'],)),
                            transmitter=wideband_transmit(tx_environment,oversample=n,noise=False)) for n in (128,256)],
                        weak_rx_resolution_512=wideband_receive(e,oversample=512,noise=False,gain_settings_db=(context['resolved_configuration']['pga_gain_db'],)),
                        scope='All-pole comparison uses the same absolute RF and loaded environment. Resolution pairs retain delivered clock tones and rail/reference movement but disable random thermal/excess-converter/aperture draws to compare the same waveform; they do not qualify a continuous phase-noise process.'))
            rows.append(dict(context,mode=mode,carrier_hz=carrier,d2h_word_hz=word,
                control_hz=e['control_hz'],control_clock_owner=e['control_clock_owner'],
                network_case=label,network=candidate,ledger=e['ledger'],
                nominal_rail_interval_v=[rail-tone_bound,rail+tone_bound],
                coherent_rail=rail_excursion(e['host_spectrum']['tones'],dc_v=rail),
                host_induced_delay_rms_s=supply_shift,
                legacy_5ps_random_jitter_allocation_s=5e-12,
                host_delay_exceeds_5ps_comparison=supply_shift>5e-12,
                delivered_phase_tones=e['delivered_phase_tones'],
                reference_fraction_tones=e['reference_fraction_tones'],
                loaded_input=e['external_clock_input'],source_dc_corners=corners,
                scope='The 5 ps comparison is diagnostic: deterministic host tones cannot be treated as independent random jitter. Rail intervals sum tone amplitudes and may be conservative. Source corners vary DC only; host capacitance/current spectra and input slew remain evaluated at nominal source voltage.'))
    result=dict(design_provenance=design.provenance(),status='selected_baseline_electrical_screen_not_complete_chip_test',complete=False,
        clock_revision='differential_v6',
        legacy_control_sections=['converter_reference_feedback','wideband_rf','wideband_rf_controls','wideband_diagnosis','return_partition','reference_return'],
        rf_converter_evidence_owner='narrowband_rf uses corrected REF_IN timing and causal SAR/input-voltage feedback. reference_payload includes assigned-ENOB controls plus moderate and weak tied-return causal feedback. converter_reference_feedback and wideband_rf retain previous-environment controls.',
        legacy_fixture_mode_current_a=MODE_CURRENT_A,cases=rows,
        wired_receiver=causal_receiver_envelope(timing_scenarios=wired_scenarios,
            channel_cases=tuple(dict.fromkeys(row['channel_case'] for row in wired_inputs))),
        wired_receiver_inputs=wired_inputs,
        wideband_rf=rf_rows,
        wideband_rf_controls=rf_controls,
        narrowband_rf=inputs['narrowband_rf'],
        converter_reference_feedback=inputs['converter_reference_feedback'],
        transmitter_wake=transmitter_wake_campaign(contract,design=design),
        wired_recovery=wired_recovery_campaign(contract,design=design),
        wired_transmit=wired_transmit_campaign(contract,design=design),
        usb_static_voltage=usb_voltage_campaign(contract,design=design),
        usb_hs_levels=usb_hs_level_campaign(contract,design=design),
        return_partition=return_partition_campaign(contract,design=design),
        reference_return=reference_return_campaign(contract,design=design),
        reference_payload=reference_payload_campaign(contract,design=design),
        wideband_diagnosis=inputs['wideband_diagnosis'],
        assumptions=['The same linear common feed/branch/return model as retained studies, not measured assembly impedance.',
            'H2D internal charge is part of the 110 mA HOST allowance, routed locally. No second timing C*V*f load is added.',
            'Reserve current is a constant load; converter, core, inactive detection and output load-change spectra still need explicit bounds.',
            'Higher-inductance case is an uncertainty probe, not an asserted process/package maximum.',
            'Timing uses the retained external source, high-impedance input and assigned supply-to-delay transfer; no autonomous PLL or GF180 qualification.'],
        missing_for_complete_baseline=['physical SAR/reference poles, comparator regeneration, mismatch and full load/noise qualification; conditional closed-loop conversion/reference-load feedback is now modeled',
            'calibrated narrowband air-boundary turnaround and broader packet coverage; wideband still uses known DATA training and ideal boundaries',
            'actual RF noise/linearity and transition-dependent current with these loaded rails',
            'corrected REF_IN timing joins wideband RF and a moderate-signal tied-return SAR feedback control; weak-wideband causal SAR and bounded driver-wake now use corrected input and supply feedback; real packet acquisition, stage-specific sensitivities and transient edge completeness remain open; wired recovery now uses corrected shared rails with independent CDR, and wired_transmit propagates nonuniform TX edges through the channel with independent peer CDR; serializer logic and driver-current feedback remain open; corrected narrowband packets retain failures',
            'generic wired RX recovery is joined; protocol-specific pad/driver, electrical startup and full duplex lifecycle remain open',
            'host current distribution per physical bond, GPIO timing and complete 8192-bit storage ceiling',
            'supply-dependent AC spectra, thermal feasibility and stage-specific device variation'],
        sources_sha256=baseline_source_hashes(),
        source_verification='Assembly-time snapshot only; full runner must verify before/after hashes')
    families={name:result[name]['cases'] for name in ('narrowband_rf',
        'converter_reference_feedback','transmitter_wake','wired_recovery','wired_transmit','usb_static_voltage','usb_hs_levels','return_partition','reference_return','reference_payload','wideband_diagnosis')}
    families.update(electrical=result['cases'],wideband_rf=result['wideband_rf'],
        wideband_rf_controls=result['wideband_rf_controls'])
    coverage={name:sorted({r['network_case'] for r in cases}) for name,cases in families.items()}
    coverage['wired_receiver']=sorted({r['impairment']['name'] for r in result['wired_receiver']['cases']})
    expected=sorted(name for name,_,_ in network_cases(design))
    if any(names!=expected for names in coverage.values()):
        raise ValueError('A joined bench omitted a package case')
    result['baseline_package_case']=BASELINE_PACKAGE_CASE
    result['package_case_coverage']=coverage
    result['package_catalog']=[dict(name=name,return_l_h=ret,die_esl_h=esl) for name,ret,esl in network_cases(design)]
    result['coverage_scope']='Every existing joined bench runs each catalog entry. This does not supply missing full-chip behaviors or protocol qualification.'
    rf_observations=[]
    for row in result['reference_payload']['cases']:
        if row['network_case']!=BASELINE_PACKAGE_CASE or row['variant']!='tied_baseline':continue
        feedback=row['weak_converter_feedback']
        observation=None if feedback is None else feedback['receiver']['gain_cases'][0]['observation']
        rf_observations.append(dict(carrier_hz=row['carrier_hz'],supply_sign=row['clock']['supply_sensitivity_sign'],
            clock_status=row['clock']['status'],feedback_converged=None if feedback is None else feedback['numerical_feedback_converged'],
            uncoded_errors=None if observation is None else observation['bpsk_errors'],
            evaluated_bits=None if observation is None else observation['evaluated_bits']))
    narrow=next(row for row in result['narrowband_rf']['cases'] if row['network_case']==BASELINE_PACKAGE_CASE)
    transmitted=next(row for row in result['wired_transmit']['cases'] if row['network_case']==BASELINE_PACKAGE_CASE)
    result['current_target_observations']=dict(
        scope='Selected differential package-target cases; single-ended amplitude and split-return controls remain explicitly separate. Numerical convergence is separate from signal acceptance. Mitigation controls do not replace baseline failures; these are fixture observations, not protocol verdicts or chip-completeness scores.',
        weak_wideband=rf_observations,
        narrowband=dict(status=narrow['status'],exercised_requests=len(narrow['cases']),
            correct_requests=sum(c['received']['correct_request'] for c in narrow['cases']),
            correct_replies=sum(bool(c['calibrated_transmission'].get('peer_correct_response',False)) for c in narrow['cases'])),
        wired_transmit=dict(status=transmitted['status'],
            zero_heldout_errors=transmitted.get('all_heldout_data_errors_zero'),
            continuously_qualified=transmitted.get('all_heldout_continuously_qualified'),
            nominal_launch_phases=transmitted.get('nominal_launch_phase_summary'),
            finite_transport_data_correct=None if not transmitted.get('finite_transport_cases') else
                all(c['flow']['fault'] is None and c['payload_bit_errors']==0 for c in transmitted['finite_transport_cases'])))
    return result



if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--internal-switching-rf',action='store_true')
    group.add_argument('--internal-decoupling',action='store_true')
    group.add_argument('--internal-damping',action='store_true')
    group.add_argument('--internal-pulses',action='store_true')
    group.add_argument('--internal-sensitivity',action='store_true')
    group.add_argument('--usb-internal',action='store_true')
    group.add_argument('--usb-rate-audit',action='store_true')
    args=parser.parse_args()
    if args.internal_decoupling or args.internal_damping or args.internal_switching_rf or args.internal_pulses or args.internal_sensitivity or args.usb_internal or args.usb_rate_audit:
        names=set(json.loads((P/'evidence/selected-baseline.json').read_text())['sources_sha256'])|{'spec/analog-architecture.json'}
        hashes={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in names}
        design=load_design();contract=design.contract
        if args.usb_rate_audit:
            result=usb_rate_feasibility_audit(design=design);name='usb-rate-audit'
        elif args.usb_internal:
            result=usb_internal_campaign(contract,design=design);name='usb-internal'
        elif args.internal_sensitivity:
            result=internal_sensitivity_campaign(contract,design=design);name='internal-sensitivity'
        elif args.internal_pulses:
            result=internal_pulse_campaign(contract,design=design);name='internal-pulses'
        elif args.internal_switching_rf:
            result=internal_switching_rf_campaign(contract,design=design);name='internal-switching-rf'
        else:
            result=internal_decoupling_campaign(contract,damping=args.internal_damping,design=design)
            name='internal-damping' if args.internal_damping else 'internal-decoupling'
        if any(hashlib.sha256((P/name).read_bytes()).hexdigest()!=value for name,value in hashes.items()):
            raise RuntimeError('Sources changed during campaign')
        result['sources_sha256']=hashes
        write_evidence(P/f'evidence/{name}.json',result)
        raise SystemExit(0)
    result=run()
    path=P/'evidence/selected-baseline.json'
    write_evidence(path,result)
    for case in result['cases']:
        print(case['mode'],case['carrier_hz']/1e9,case['network_case'],
              'rail V',case['nominal_rail_interval_v'],
              'host delay ps',case['host_induced_delay_rms_s']*1e12)
    print('Complete baseline test remains open. Report:',path)
