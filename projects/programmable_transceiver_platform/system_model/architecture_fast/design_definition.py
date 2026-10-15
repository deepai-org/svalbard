"""Immutable shared design input for integrated models and their evidence.

The JSON specifications own values; this module owns loading and structural
validation. Returned documents are copies, so a test cannot mutate another
model's design. Numerical primitives may continue using independent inputs.
"""
from dataclasses import dataclass, field
import hashlib
import json
import math
from types import MappingProxyType
from collections.abc import Mapping
from pathlib import Path

P = Path(__file__).resolve().parents[2]


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError('Design must contain finite JSON values') from error


def validate_contract_provenance(contract, provenance):
    """Reject mixed shared-design inputs; unbound mathematical fixtures are allowed."""
    if provenance is None:
        return
    expected=provenance.get('documents',{}).get('spec/contract.json')
    actual=hashlib.sha256(_canonical(contract).encode()).hexdigest()
    if expected is None or actual!=expected:
        raise ValueError('Contract conflicts with shared design provenance')


def _required(document, path):
    value = document
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f'Missing required design parameter: {path}')
        value = value[key]
    return value


def validate_transport_binding(environment):
    """Validate shared transport inputs; independent numerical fixtures stay unbound."""
    provenance=environment.get('design_provenance')
    if 'design_provenance' not in environment:
        if 'inventory_current_report' in environment or 'resolved_configuration' in environment:
            raise ValueError('Inventory-bound transport environment requires design provenance')
        return None
    if not isinstance(provenance,dict) or not provenance:
        raise ValueError('Shared transport requires design provenance')
    parameters=environment.get('transport_parameters')
    if not isinstance(parameters,dict) or 'startup_s' not in parameters:
        raise ValueError('Design-bound environment missing startup transport parameter')
    for key in ('startup_s','h2d_word_hz','d2h_word_hz','control_hz'):
        if key not in parameters:
            raise ValueError('Design-bound environment missing transport parameter: '+key)
        value=parameters[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite shared transport parameter required: '+key)
    if 'control_hz' not in environment:
        raise ValueError('Design-bound transport requires control clock')
    if environment['control_hz']!=parameters['control_hz']:
        raise ValueError('Control clock conflicts with shared transport parameters')
    config=environment.get('resolved_configuration')
    if not isinstance(config,dict) or not config:
        raise ValueError('Shared transport requires resolved configuration')
    if any(config.get(key)!=value for key,value in provenance.items()):
        raise ValueError('Transport configuration conflicts with environment design provenance')
    for parameter,field in (('h2d_word_hz','h2d_word_hz'),('d2h_word_hz','host_word_hz'),('control_hz','control_hz')):
        if field not in config or parameters[parameter]!=config[field]:
            raise ValueError('Transport rates conflict with resolved configuration')
    return dict(parameters)


def _validate(contract, architecture):
    for path in ('transport', 'physical_services.sar_timing.maximum_conversion_s',
                 'physical_services.sar_timing.startup.assigned_guard_s',
                 'physical_services.host_output.full_rate_external_load_target_f',
                 'physical_services.external_clock_input'):
        _required(contract, path)
    for key in ('clock_hz','edges'):
        path='transport.profiles.ddr156.'+key
        value=_required(contract,path)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite framed host parameter required: '+path)
    if contract['transport']['profiles']['ddr156']['edges']!=2:
        raise ValueError('Selected framed host service requires DDR edges')
    for key in ('ingress_bits_per_source','egress_bits_per_source'):
        path='transport.scheduling.'+key
        value=_required(contract,path)
        if type(value) is not int or value<=0:
            raise ValueError('Positive integer transport allocation required: '+path)
    status=_required(contract,'transport.scheduling.fifo_budget_status')
    if not isinstance(status,str) or not status.strip():
        raise ValueError('Explicit transport allocation status required')
    startup=_required(contract,'physical_services.sar_timing.startup.assigned_guard_s')
    if isinstance(startup,bool) or not isinstance(startup,(int,float)) or not math.isfinite(startup) or startup<=0:
        raise ValueError('Positive finite shared startup guard required')
    divider=_required(architecture,'control_semantics.scheduler_clock_divider')
    if type(divider) is not int or divider<=0:
        raise ValueError('Positive integer scheduler clock divider required')
    for path in ('blocks', 'nets', 'operating_modes', 'resource_policy'):
        _required(architecture, path)
    for path in ('rf_interoperability.tx_error_allocation',
                 'rf_interoperability.tx_spectral_measurement.rbw_hz',
                 'rf_interoperability.tx_spectral_measurement.relative_mask_offset_hz',
                 'rf_interoperability.tx_spectral_measurement.relative_mask_db'):
        _required(architecture,path)
    voltage=_required(contract,'physical_services.host_output.voltage_v')
    if isinstance(voltage,bool) or not isinstance(voltage,(int,float)) or not math.isfinite(voltage) or voltage<=0:
        raise ValueError('Positive finite host output voltage required')
    for key in ('analog_supply_v','digital_supply_v'):
        value=_required(architecture,'blocks.board.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite board supply required: '+key)
    target=_required(architecture,'blocks.refbuf.parameters.target_v')
    if isinstance(target,bool) or not isinstance(target,(int,float)) or not math.isfinite(target) or target<=0:
        raise ValueError('Positive finite converter reference target required')
    for key in ('gain_reference_v','headroom_reference_v'):
        value=_required(architecture,'model_assumptions.rf_receive_supply.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite RF receive supply reference required: '+key)
    elasticity=_required(architecture,'model_assumptions.rf_receive_supply.parameters.gain_supply_elasticity')
    if isinstance(elasticity,bool) or not isinstance(elasticity,(int,float)) or not math.isfinite(elasticity) or elasticity<0:
        raise ValueError('Nonnegative finite RF gain supply elasticity required')
    preparation=_required(architecture,'rf_interoperability.fpga_tx_preparation')
    for key in ('wideband_correction_enabled','received_pilot_frequency_update'):
        if type(preparation.get(key)) is not bool:raise ValueError('Boolean FPGA preparation control required: '+key)
    for key in ('taps','coefficient_fraction_bits','polyphase_resampler_span','polyphase_resampler_fraction_bits'):
        value=preparation.get(key)
        if type(value) is not int or value<1:raise ValueError('Positive integer FPGA preparation control required: '+key)
    if preparation['taps']<3 or preparation['taps']%2!=1:raise ValueError('Odd FPGA correction length >=3 required')
    tx_reference=_required(architecture,'blocks.rfdriver.parameters.gain_reference_v')
    if isinstance(tx_reference,bool) or not isinstance(tx_reference,(int,float)) or not math.isfinite(tx_reference) or tx_reference<=0:
        raise ValueError('Positive finite TX gain reference required')
    gain_reference=_required(architecture,'model_assumptions.wired_supply_gain.parameters.reference_voltage_v')
    if isinstance(gain_reference,bool) or not isinstance(gain_reference,(int,float)) or not math.isfinite(gain_reference) or gain_reference<=0:
        raise ValueError('Positive finite wired gain reference voltage required')
    _required(architecture,'blocks.board.parameters.nominal_temperature_c')
    _required(architecture,'blocks.board.parameters.temperature_c')
    for key in ('dc_gain','zero_s','pole_s'):
        value=_required(architecture,'blocks.ctle.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite CTLE parameter required: '+key)
    ctle=architecture['blocks']['ctle']['parameters']
    if ctle['zero_s']<=ctle['pole_s']:
        raise ValueError('CTLE zero time constant must exceed pole time constant')
    cdr=_required(architecture,'blocks.cdr.parameters')
    phase_steps=cdr.get('phase_control_steps',0)
    if type(phase_steps) is not int or phase_steps<0:
        raise ValueError('Nonnegative integer phase control steps required')
    period_lsb=cdr.get('period_control_lsb_ppm',0.)
    if isinstance(period_lsb,bool) or not isinstance(period_lsb,(int,float)) or not math.isfinite(period_lsb) or period_lsb<0:
        raise ValueError('Finite nonnegative period control resolution required')
    if cdr.get('detector_model')=='phase_bank':
        bins=cdr.get('detector_phase_bins');span=cdr.get('detector_phase_span_ui');steps=cdr.get('phase_steps')
        if (type(bins) is not int or not 2<=bins<=128 or type(steps) is not int or steps<1 or
                isinstance(span,bool) or not isinstance(span,(float,int)) or not math.isfinite(span) or not 0<span<.5):
            raise ValueError('Invalid phase-bank geometry')
        spacing=steps*2*span/bins
        if spacing<1 or not math.isclose(spacing,round(spacing),abs_tol=1e-12):
            raise ValueError('Phase bank requires realizable integer clock slots')
        if architecture['blocks']['slicer']['parameters'].get('tracking_sampler_count',0)<bins+2:
            raise ValueError('Phase bank requires a DATA sampler and every boundary slot')
        net=_required(architecture,'nets.phase_code')
        width=math.ceil(math.log2(bins))+2  # bin index, valid and transition polarity
        if (net.get('source')!='slicer.phase_code' or 'cdr.phase_code' not in net.get('sinks',[]) or
                net.get('electrical',{}).get('conductors')!=width):
            raise ValueError('Phase-bank encoder connection or width mismatch')
        for block,direction in (('slicer','out'),('cdr','in')):
            port=_required(architecture,f'blocks.{block}.ports.phase_code')
            if port.get('net')!='phase_code' or port.get('direction')!=direction:
                raise ValueError('Phase-bank encoder port mismatch')
        delay=cdr.get('periodic_clock_compute_delay_s')
        if delay is not None:
            if isinstance(delay,bool) or not isinstance(delay,(float,int)) or not math.isfinite(delay) or delay<=0:
                raise ValueError('Positive periodic-clock processing delay required')
            timeout=cdr.get('acquisition_timeout_ui')
            maximum=_required(architecture,'control_fields')['cdr.config']['fields']['acquisition_timeout_ui']['maximum']
            if type(timeout) is not int or not 1<=timeout<=maximum:
                raise ValueError('Periodic-clock acquisition timeout outside control range')
            if cdr.get('periodic_observation_link') is not None:
                from timing_services import PeriodicObservationLink
                PeriodicObservationLink(architecture['blocks']['cdr']['parameters']['line_rate_hz'][-1],**cdr['periodic_observation_link'])
    jitter=_required(architecture,'blocks.cdr.parameters.detector_jitter_rms_s')
    if isinstance(jitter,bool) or not isinstance(jitter,(int,float)) or not math.isfinite(jitter) or jitter<0:
        raise ValueError('Finite nonnegative CDR detector jitter required')
    holdover=_required(architecture,'blocks.cdr.parameters.holdover_bits')
    if type(holdover) is not int or holdover<=0:
        raise ValueError('Positive integer CDR holdover required')
    for key in ('supply_sensitivity_ps_per_mv','delay_pole_hz'):
        value=_required(architecture,'blocks.cdr.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key=='delay_pole_hz' and value==0):
            raise ValueError('Invalid CDR supply-delay parameter: '+key)
    for key in ('bit_durations_s','comparator_s','sample_resistance_ohm','dac_effective_cap_f',
                'dac_tau_s','comparator_noise_rms_v','diagnostic_reference_effective_cap_per_lane_f'):
        _required(architecture,'model_assumptions.paired_sar.parameters.'+key)
    comparator_noise=_required(architecture,'model_assumptions.paired_sar.parameters.comparator_noise_rms_v')
    if (isinstance(comparator_noise,bool) or not isinstance(comparator_noise,(int,float))
            or not math.isfinite(comparator_noise) or comparator_noise<0):
        raise ValueError('Finite nonnegative comparator RMS noise required')
    for key in ('enob','aperture_rms_s'):
        _required(architecture,'model_assumptions.paired_dac.parameters.'+key)
    aperture=_required(architecture,'model_assumptions.paired_adc.parameters.aperture_rms_s')
    if isinstance(aperture,bool) or not isinstance(aperture,(int,float)) or not math.isfinite(aperture) or aperture<0:
        raise ValueError('Finite nonnegative ADC aperture jitter required')
    sensitivity=_required(contract,'physical_services.external_clock_input.supply_sensitivity_ps_per_mv')
    if isinstance(sensitivity,bool) or not isinstance(sensitivity,(int,float)) or not math.isfinite(sensitivity) or sensitivity<0:
        raise ValueError('Invalid clock supply sensitivity')
    pole=_required(contract,'physical_services.external_clock_input.supply_delay_pole_hz')
    if isinstance(pole,bool) or not isinstance(pole,(int,float)) or not math.isfinite(pole) or pole<=0:
        raise ValueError('Invalid clock supply delay pole')
    for key in ('supply_fraction_per_v','supply_pole_hz'):
        value=_required(architecture,'blocks.refbuf.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key=='supply_pole_hz' and value==0):
            raise ValueError('Invalid reference supply coupling parameter: '+key)
    for key in ('gain_imbalance_db','phase_error_deg','lo_feedthrough','cubic'):
        value=_required(architecture,'model_assumptions.rf_output.parameters.'+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Finite RF output impairment required: '+key)
        if key=='cubic' and value<0:
            raise ValueError('Nonnegative RF output compression required')
    for key in ('tau_s','launch_s','output_threshold_v'):
        _required(architecture,'model_assumptions.paired_sar_comparator.parameters.'+key)
    for direction in ('h2d','d2h'):
        charge=_required(architecture,'model_assumptions.host_switching.parameters.'+direction+'_internal_charge_c')
        if not isinstance(charge,(int,float)) or isinstance(charge,bool) or not math.isfinite(charge) or charge<0:
            raise ValueError('Finite nonnegative host transition charge required')
    budget_path='direct_stream_service.budget.'
    _required(architecture,budget_path+'host_edges')
    for key in ('host_hz','line_hz','tx_fifo_read_hz','fpga_decision_s','rx_tail_ui',
                'packing_ui','quiet_ui','rx_cdc_host_cycles','rx_tail_beats','fpga_capture_cycles',
                'tx_phase_cycles','tx_start_and_prefill_beats','tx_cdc_cycles','retime_ui',
                'analog_output_s','board_margin_s','deadline_s'):
        value=_required(architecture,budget_path+key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('Invalid direct-stream timing allocation: '+key)
        if key in ('host_hz','line_hz','tx_fifo_read_hz','deadline_s') and value==0:
            raise ValueError('Positive direct-stream timing allocation required: '+key)
    modes = architecture['operating_modes']
    for name, block in architecture['blocks'].items():
        for path in ('parameters', 'supply', 'resource_allocation.current_budget_ma'):
            _required(architecture, f'blocks.{name}.{path}')
        for mode in modes:
            amount = _required(architecture, f'blocks.{name}.resource_allocation.current_budget_ma.{mode}')
            if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
                raise ValueError(f'Invalid current allocation: {name}/{mode}')
    for name in ('rxfilter_i','rxfilter_q'):
        order=_required(architecture,f'blocks.{name}.parameters.order')
        cutoff=_required(architecture,f'blocks.{name}.parameters.cutoff_hz')
        if type(order) is not int or order<=0:
            raise ValueError('Positive integer filter order required: '+name)
        if (not isinstance(cutoff,list) or len(cutoff)!=2 or
                any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in cutoff)
                or not 0<cutoff[0]<=cutoff[1]):
            raise ValueError('Ordered positive filter cutoff range required: '+name)
    for name in ('adc_i', 'adc_q', 'dac_i', 'dac_q'):
        for key in ('native_bits', 'transport_bits', 'sample_rate_max_hz'):
            _required(architecture, f'blocks.{name}.parameters.{key}')
    for name in ('adc_i','adc_q','dac_i','dac_q'):
        params=architecture['blocks'][name]['parameters']
        if any(type(params[key]) is not int or params[key]<=0 for key in ('native_bits','transport_bits')):
            raise ValueError('Positive integer converter widths required: '+name)
        if params['native_bits']>params['transport_bits']:
            raise ValueError('Native converter width exceeds transport width: '+name)
        rate=params['sample_rate_max_hz']
        if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate) or rate<=0:
            raise ValueError('Positive finite converter sample rate required: '+name)
    noise=architecture['model_assumptions']['paired_dac']['parameters']
    for key in ('enob','aperture_rms_s'):
        value=noise[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Finite numeric DAC noise allocation required: '+key)
    if not 1<=noise['enob']<=min(architecture['blocks'][name]['parameters']['native_bits'] for name in ('dac_i','dac_q')):
        raise ValueError('DAC ENOB must fit native precision')
    if noise['aperture_rms_s']<0:
        raise ValueError('Nonnegative DAC aperture jitter required')
    for name in ('adc_i','adc_q'):
        enob=_required(architecture,f'blocks.{name}.parameters.enob_target')
        if isinstance(enob,bool) or not isinstance(enob,(int,float)) or not 1<=enob<=architecture['blocks'][name]['parameters']['native_bits']:
            raise ValueError('ADC ENOB target must fit native precision: '+name)
    for name in ('dac_i','dac_q'):
        peak=_required(architecture,f'blocks.{name}.parameters.differential_peak_v')
        if isinstance(peak,bool) or not isinstance(peak,(int,float)) or not math.isfinite(peak) or peak<=0:
            raise ValueError('Positive finite DAC differential peak required: '+name)
    for key in ('nominal_gain','gain_range','bias_current_a','source_r_ohm_differential',
                'load_ohm_differential','headroom_per_rail_v'):
        _required(architecture,'blocks.rfdriver.parameters.'+key)
    driver=architecture['blocks']['rfdriver']['parameters']
    for key in ('nominal_gain','bias_current_a','source_r_ohm_differential',
                'load_ohm_differential','headroom_per_rail_v'):
        value=driver[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('Finite nonnegative RF driver parameter required: '+key)
        if key in ('nominal_gain','bias_current_a','load_ohm_differential') and value==0:
            raise ValueError('Positive RF driver parameter required: '+key)
    gain_bits=_required(architecture,'blocks.rfdriver.parameters.gain_bits')
    if type(gain_bits) is not int or not 1<=gain_bits<=16:
        raise ValueError('RF driver gain resolution must be an integer from 1 to 16 bits')
    gains=driver['gain_range']
    if (not isinstance(gains,list) or len(gains)!=2 or
            any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in gains) or
            not 0<gains[0]<=driver['nominal_gain']<=gains[1]):
        raise ValueError('RF driver nominal gain must lie inside its positive gain range')
    for name in ('pga_i', 'pga_q'):
        peak=_required(architecture, f'blocks.{name}.parameters.differential_peak_limit_v')
        if isinstance(peak,bool) or not isinstance(peak,(int,float)) or not math.isfinite(peak) or peak<=0:
            raise ValueError('Positive finite PGA peak limit required: '+name)
        tau=_required(architecture, f'blocks.{name}.parameters.gain_response_tau_s')
        if isinstance(tau,bool) or not isinstance(tau,(int,float)) or not math.isfinite(tau) or tau<=0:
            raise ValueError('Positive finite PGA response time required: '+name)
        gains=_required(architecture, f'blocks.{name}.parameters.gain_db')
        if (not isinstance(gains,list) or not gains or
                any(isinstance(gain,bool) or not isinstance(gain,(int,float)) for gain in gains) or
                len(set(gains))!=len(gains)):
            raise ValueError('PGA gain codes must be a nonempty unique numeric list: '+name)
    gains=_required(architecture,'blocks.lna.parameters.gain_db')
    if not isinstance(gains,list) or not gains or any(isinstance(g,bool) or not isinstance(g,(int,float)) or not math.isfinite(g) for g in gains) or len(set(gains))!=len(gains):
        raise ValueError('LNA gains must be a nonempty unique finite numeric list')
    for key in ('noise_figure_db','iip3_dbm'):
        _required(architecture, 'blocks.lna.parameters.'+key)
    for key in ('reservoir_f', 'output_r_ohm', 'source_limit_a', 'quiescent_current_a'):
        _required(architecture, f'blocks.refbuf.parameters.{key}')
    for key in ('rf_sample_dividers', 'rf_host_word_divider', 'wire_line_rate_hz', 'wire_host_divider_range'):
        _required(architecture, f'blocks.clocktree.parameters.{key}')
    package=_required(architecture,'model_assumptions.reference_input_package.parameters')
    for key in ('bond_l_h','source_r_ohm','mutual_l_h'):
        value=_required(package,key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key!='mutual_l_h' and value==0):
            raise ValueError('Invalid reference package parameter: '+key)
    if package['mutual_l_h']>=package['bond_l_h']:
        raise ValueError('Reference package mutual inductance must be below self inductance')
    source_path='physical_services.external_clock_input.source_differential_peak_v'
    source_peak=_required(contract,source_path)
    if isinstance(source_peak,bool) or not isinstance(source_peak,(int,float)) or not math.isfinite(source_peak) or source_peak<=0:
        raise ValueError('Positive finite differential reference source peak required')
    if 'source_differential_peak_v' in architecture['blocks']['refpad']['parameters']:
        raise ValueError('Duplicate reference source amplitude parameter')
    if _required(architecture,'blocks.refpad.shared_parameter_sources.source_differential_peak_v')!='contract.'+source_path:
        raise ValueError('Invalid reference source amplitude owner')
    capacitance=_required(architecture,'blocks.refpad.parameters.capacitance_f_per_leg')
    if isinstance(capacitance,bool) or not isinstance(capacitance,(int,float)) or not math.isfinite(capacitance) or capacitance<=0:
        raise ValueError('Positive finite reference pad capacitance required')
    for local,remote in (('supply_sensitivity_ps_per_mv','supply_sensitivity_ps_per_mv'),
                         ('delay_pole_hz','supply_delay_pole_hz')):
        if local in architecture['blocks']['refinput']['parameters']:
            raise ValueError('Duplicate reference timing parameter: '+local)
        owner=_required(architecture,'blocks.refinput.shared_parameter_sources.'+local)
        if owner!='contract.physical_services.external_clock_input.'+remote:
            raise ValueError('Invalid reference timing parameter owner: '+local)
    _required(architecture, 'blocks.refinput.parameters.high_frequency_hz')
    _required(architecture, 'blocks.refinput.parameters.receiver_noise_v')
    # Validate the complete selected pad before any network factory can run.
    for block,keys in (
            ('usbhs',('drive_current_a','termination_ohm_per_leg','squelch_v')),
            ('usbfs',('pullup_ohm','pulldown_ohm','effective_output_r_ohm'))):
        for key in keys:
            value=_required(architecture,'blocks.'+block+'.parameters.'+key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
                raise ValueError('Positive finite local USB pad parameter required: '+key)
    network=_required(architecture,'pad_behavioral_contract.shared_wired_network')
    for key in ('base_shunt_cap_f_per_leg','inactive_branch_cap_f_per_leg','mutual_cap_f',
                'divider_cap_f_per_leg','divider_top_ohm','divider_bottom_ohm',
                'divider_off_ohm','serial_differential_termination_ohm'):
        value=_required(network,key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            raise ValueError('Positive finite shared pad network parameter required: '+key)
    budget=_required(architecture,'blocks.wirepad.parameters.capacitance_f_per_leg')
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or budget<=0:
        raise ValueError('Positive finite wired pad capacitance required')
    if not math.isclose(network['base_shunt_cap_f_per_leg']+network['inactive_branch_cap_f_per_leg']+
                        2*network['mutual_cap_f'],budget,rel_tol=1e-9,abs_tol=1e-24):
        raise ValueError('Wired pad odd-mode capacitance differs from architecture budget')
    skew=_required(contract,'physical_services.external_clock_input.source_leg_skew_s')
    if isinstance(skew,bool) or not isinstance(skew,(int,float)) or not math.isfinite(skew):
        raise ValueError('Finite signed reference source leg skew required')
    sensing=_required(architecture,'model_assumptions.wired_pad_sensing.parameters')
    if (not isinstance(sensing,dict) or set(sensing)!={'single_ended_low_v','single_ended_high_v'} or
            any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in sensing.values()) or
            not 0<=sensing['single_ended_low_v']<sensing['single_ended_high_v']):
        raise ValueError('Complete ordered shared pad sensing thresholds required')
    driver=_required(architecture,'model_assumptions.wired_pad_driver.parameters')
    required={'reference_supply_v','reference_pad_v','supply_fraction_per_v',
              'output_conductance_s','trim','compliance_headroom_v','shunt_leakage_ohm'}
    if not isinstance(driver,dict) or set(driver)!=required:
        raise ValueError('Complete shared wired-pad driver assumptions required')
    for key,value in driver.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Finite wired-pad driver assumptions required')
        if key!='supply_fraction_per_v' and (value<0 or
                (key not in ('reference_pad_v','output_conductance_s') and value==0)):
            raise ValueError('Invalid wired-pad driver assumption: '+key)
    acceptance=_required(architecture,'model_assumptions.reference_input_acceptance.parameters')
    if not isinstance(acceptance,dict) or set(acceptance)!={'threshold_v','effective_peak_limit_v','leg_peak_limit_v'}:
        raise ValueError('Complete reference input acceptance parameters required')
    for key,value in acceptance.items():
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (key!='threshold_v' and value<=0):
            raise ValueError('Invalid reference input acceptance parameter: '+key)
    if abs(acceptance['threshold_v'])>=acceptance['effective_peak_limit_v']:
        raise ValueError('Reference threshold must lie inside effective input envelope')
    _required(architecture, 'blocks.clocktree.parameters.downstream_stage_rms_s')
    _required(architecture, 'blocks.power.parameters.shared_return_l_h')
    _required(architecture, 'blocks.power.parameters.bond_l_h')
    _required(architecture, 'blocks.power.parameters.reduced_pdn_model.return_r_ohm')
    for key in ('feed_r','feed_l','package_r','die_c','board_c','board_esr','board_esl','die_esr','die_esl'):
        _required(architecture, 'blocks.power.parameters.reduced_pdn_model.network.'+key)


@dataclass(frozen=True)
class DesignDefinition:
    """One validated snapshot, independent of subsequent file/dictionary edits."""
    _contract_json: str
    _architecture_json: str
    _experiment_json: str = '[]'

    def __post_init__(self):
        contract = json.loads(self._contract_json)
        architecture = json.loads(self._architecture_json)
        _validate(contract, architecture)
        object.__setattr__(self, '_contract_json', _canonical(contract))
        object.__setattr__(self, '_architecture_json', _canonical(architecture))
        experiments=json.loads(self._experiment_json)
        if not isinstance(experiments,list):
            raise ValueError('Circuit experiment history must be a list')
        object.__setattr__(self, '_experiment_json', _canonical(experiments))

    @classmethod
    def from_documents(cls, contract, architecture):
        return cls(_canonical(contract), _canonical(architecture))

    @property
    def contract(self):
        return json.loads(self._contract_json)

    @property
    def architecture(self):
        return json.loads(self._architecture_json)

    @property
    def fingerprint(self):
        content = '{"contract":' + self._contract_json + ',"architecture":' + self._architecture_json + '}'
        return hashlib.sha256(content.encode()).hexdigest()

    def configure(self, **settings):
        return ResolvedConfiguration(self, **settings)

    def hypothetical(self, *, reason, changes):
        """Fork an explicitly hypothetical circuit; never edit the base snapshot.

        Keys address existing block/device-model parameters or the scheduler clock divider.
        Schema/topology changes require an intentional adapter implementation.
        """
        if not isinstance(reason,str) or not reason.strip():
            raise ValueError('Hypothetical circuit change requires a reason')
        if not isinstance(changes,dict) or not changes:
            raise ValueError('At least one circuit parameter change required')
        architecture=self.architecture
        entries=[]
        for path,value in sorted(changes.items()):
            parts=path.split('.')
            parameter_path=(len(parts)>=4 and parts[0] in ('blocks','model_assumptions') and parts[2]=='parameters')
            if not parameter_path and path!='control_semantics.scheduler_clock_divider':
                raise ValueError('Circuit changes must address existing block or device-model parameters')
            before=_required(architecture,path)
            parent=architecture
            for part in parts[:-1]:parent=parent[part]
            parent[parts[-1]]=json.loads(_canonical(value))
            entries.append(dict(path=path,before=before,after=value))
        history=json.loads(self._experiment_json)
        history.append(dict(kind='hypothetical_circuit',parent_design_fingerprint=self.fingerprint,
                            reason=reason,changes=entries))
        return DesignDefinition(self._contract_json,_canonical(architecture),_canonical(history))

    def provenance(self):
        return dict(design_fingerprint=self.fingerprint, fingerprint_format='canonical-json-sha256-v1',
                    circuit_experiments=json.loads(self._experiment_json),
                    documents={name: hashlib.sha256(content.encode()).hexdigest()
                               for name, content in (('spec/contract.json', self._contract_json),
                                                     ('spec/analog-architecture.json', self._architecture_json))})


def load_design(root=None):
    """Load both authoritative documents once; missing data never gets defaults."""
    root = P if root is None else Path(root)
    return DesignDefinition((root/'spec/contract.json').read_text(),
                            (root/'spec/analog-architecture.json').read_text())


def resolve_tx_gain(driver, requested):
    """Resolve a requested analog gain to the shared uniform hardware codebook."""
    low,high=driver['gain_range']
    if (isinstance(requested,bool) or not isinstance(requested,(int,float)) or
            not math.isfinite(requested) or not low<=requested<=high):
        raise ValueError('TX gain outside the design range')
    levels=2**driver['gain_bits']-1
    code=0 if low==high else round((requested-low)/(high-low)*levels)
    return code,low+code*(high-low)/levels


@dataclass(frozen=True)
class ResolvedConfiguration:
    """Resolved source, payload and host clocks; not a performance qualification.

    More timing topologies will be added as their existing adapters migrate.
    Unsupported settings fail rather than being interpreted as another topology.
    """
    design: DesignDefinition
    engine: str
    direction: str
    reference_hz: float
    sample_divider: int | None = None
    pga_gain_db: float | None = None
    lna_gain_db: float | None = None
    tx_gain: float | None = None
    host_divider: int | None = None
    line_rate_bps: float | None = None
    wired_pad_path: str = 'serial'
    host_clock_source: str = 'reference_divider'
    host_input_hz: float | None = None
    cdr_periodic_tracking: bool = False
    clock_source: str = 'external_high'

    def __post_init__(self):
        if not isinstance(self.design, DesignDefinition):
            raise TypeError('A shared design snapshot is required')
        if type(self.cdr_periodic_tracking) is not bool:
            raise ValueError('Periodic tracking enable must be boolean')
        if self.cdr_periodic_tracking and (self.engine != 'wire' or self.direction not in ('rx','duplex') or self.wired_pad_path != 'serial'):
            raise ValueError('Periodic tracking requires serial wired receive')
        architecture = self.design.architecture
        blocks = architecture['blocks']
        clock = blocks['clocktree']['parameters']
        if self.clock_source not in ('external_high','forwarded_word'):
            raise ValueError('Unknown reference clock topology')
        if self.clock_source=='forwarded_word' and self.engine!='wire':
            raise ValueError('Forwarded word synthesis requires wired engine')
        low, high = blocks['refinput']['parameters'][
            'low_frequency_hz' if self.clock_source=='forwarded_word' else 'high_frequency_hz']
        if (isinstance(self.reference_hz, bool) or not isinstance(self.reference_hz, (int, float))
                or not math.isfinite(self.reference_hz) or not low <= self.reference_hz <= high):
            raise ValueError('Reference outside the selected input frequency range')
        if self.engine == 'rf':
            if self.host_clock_source not in ('reference_divider','h2d_divided') or self.host_input_hz is not None:
                raise ValueError('Unsupported RF host clock topology')
            if self.direction not in ('rx', 'tx'):
                raise ValueError('RF requires exclusive rx or tx direction')
            if self.line_rate_bps is not None or self.wired_pad_path != 'serial':
                raise ValueError('Wired settings supplied to RF engine')
            if type(self.sample_divider) is not int or self.sample_divider not in clock['rf_sample_dividers']:
                raise ValueError('Unsupported RF sample divider')
            if self.host_clock_source=='reference_divider':
                if self.host_divider is None:
                    object.__setattr__(self, 'host_divider', clock['rf_host_word_divider'])
                if self.host_divider != clock['rf_host_word_divider'] or type(self.host_divider) is not int:
                    raise ValueError('Unsupported carrier-derived RF host divider')
            elif self.host_divider is not None:
                raise ValueError('Stable H2D-derived RF clock bypasses carrier divider')
            converters = ('adc_i', 'adc_q') if self.direction == 'rx' else ('dac_i', 'dac_q')
            if any(self.sample_hz > blocks[name]['parameters']['sample_rate_max_hz'] for name in converters):
                raise ValueError('Sample rate exceeds converter allocation')
            if self.direction == 'rx':
                if self.tx_gain is not None:
                    raise ValueError('TX gain supplied to receive configuration')
                if self.lna_gain_db is None:
                    object.__setattr__(self,'lna_gain_db',max(blocks['lna']['parameters']['gain_db']))
                if isinstance(self.lna_gain_db,bool) or self.lna_gain_db not in blocks['lna']['parameters']['gain_db']:
                    raise ValueError('Unsupported LNA gain setting')
                if isinstance(self.pga_gain_db, bool) or any(
                    self.pga_gain_db not in blocks[name]['parameters']['gain_db'] for name in ('pga_i', 'pga_q')
                ):
                    raise ValueError('PGA setting is not supported by both I/Q lanes')
            elif self.pga_gain_db is not None or self.lna_gain_db is not None:
                raise ValueError('RX PGA setting supplied to transmit configuration')
            if self.direction=='tx':
                driver=blocks['rfdriver']['parameters']
                if self.tx_gain is None:
                    object.__setattr__(self,'tx_gain',driver['nominal_gain'])
                resolve_tx_gain(driver,self.tx_gain)
        elif self.engine == 'wire':
            if self.direction not in ('rx', 'tx', 'duplex'):
                raise ValueError('Unknown wired direction')
            if self.sample_divider is not None or self.pga_gain_db is not None or self.lna_gain_db is not None or self.tx_gain is not None:
                raise ValueError('RF settings supplied to wired engine')
            if self.wired_pad_path not in ('serial', 'bidirectional'):
                raise ValueError('Unknown wired pad path')
            if self.host_clock_source=='reference_divider':
                minimum, maximum = clock['wire_host_divider_range']
                if type(self.host_divider) is not int or not minimum <= self.host_divider <= maximum:
                    raise ValueError('Explicit supported wired host divider required')
                if self.host_input_hz is not None:
                    raise ValueError('External host rate supplied to divided-reference host clock')
            elif self.host_clock_source=='host_follow':
                ceiling=architecture['direct_stream_service']['budget']['host_hz']
                if self.host_divider is not None:
                    raise ValueError('Host-follow bypasses the reference-to-host divider')
                if (isinstance(self.host_input_hz,bool) or not isinstance(self.host_input_hz,(int,float))
                        or not math.isfinite(self.host_input_hz) or not 0<self.host_input_hz<=ceiling):
                    raise ValueError('Host-follow input exceeds the selected SDR service range')
            else:
                raise ValueError('Unknown wired host clock topology')
            if self.line_rate_bps is None:
                object.__setattr__(self, 'line_rate_bps', self.wire_clock_hz)
            minimum, maximum = clock['wire_line_rate_hz']
            if (isinstance(self.line_rate_bps, bool) or not isinstance(self.line_rate_bps, (int, float))
                    or not math.isfinite(self.line_rate_bps) or not minimum <= self.line_rate_bps <= maximum
                    or not math.isclose(self.line_rate_bps,self.wire_clock_hz,rel_tol=1e-12)):
                raise ValueError('Wired line rate conflicts with selected clock topology')
        else:
            raise ValueError('Unknown engine')
        if self.clock_source=='forwarded_word':
            self.wire_output_divider  # Validate the actual synthesis path now.

    @property
    def wire_clock_hz(self):
        ratio=self.design.architecture['blocks']['clocktree']['parameters']['forwarded_ratio']
        return self.reference_hz*(ratio if self.clock_source=='forwarded_word' else 1)

    @property
    def wire_output_divider(self):
        if self.clock_source!='forwarded_word':return 1
        a=self.design.architecture
        low,high=a['blocks']['wirepll']['parameters']['nominal_vco_hz']
        choices=[d for d in a['blocks']['clocktree']['parameters']['wire_output_dividers']
                 if low<=self.wire_clock_hz*d<=high]
        if not choices:raise ValueError('No VCO/output-divider combination for forwarded clock')
        return min(choices)

    @property
    def clock_domains(self):
        return dict(input_reference_hz=self.reference_hz,
            wired_bit_hz=self.wire_clock_hz if self.engine=='wire' else None,
            converter_hz=self.sample_hz,host_d2h_word_hz=self.host_word_hz,
            host_h2d_word_hz=self.h2d_word_hz,control_hz=self.control_hz,
            synthesis_required=self.clock_source=='forwarded_word',
            wire_output_divider=self.wire_output_divider if self.engine=='wire' else None,
            wire_vco_hz=self.wire_clock_hz*self.wire_output_divider if self.clock_source=='forwarded_word' else None,
            host_stable_during_rf_hop=self.engine=='rf' and self.host_clock_source=='h2d_divided')

    @property
    def tx_gain_code(self):
        if self.engine!='rf' or self.direction!='tx':return None
        return resolve_tx_gain(self.design.architecture['blocks']['rfdriver']['parameters'],self.tx_gain)[0]

    @property
    def resolved_tx_gain(self):
        if self.engine!='rf' or self.direction!='tx':return None
        return resolve_tx_gain(self.design.architecture['blocks']['rfdriver']['parameters'],self.tx_gain)[1]

    @property
    def sample_hz(self):
        return self.reference_hz / self.sample_divider if self.engine == 'rf' else None

    @property
    def host_word_hz(self):
        if self.host_clock_source=='host_follow':return self.host_input_hz
        if self.host_clock_source=='h2d_divided':
            # H2D / 2 physical D2H clock, DDR: one D2H word per H2D cycle.
            return self.h2d_clock_hz
        return (self.wire_clock_hz if self.engine=='wire' else self.reference_hz)/self.host_divider

    @property
    def h2d_word_hz(self):
        if self.host_clock_source=='host_follow':
            return self.host_word_hz
        # Selected full-rate framed service; numeric rate has one contract owner.
        profile=self.design.contract['transport']['profiles']['ddr156']
        return profile['clock_hz']*profile['edges']

    @property
    def h2d_clock_hz(self):
        return self.host_input_hz if self.host_clock_source=='host_follow' else self.design.contract['transport']['profiles']['ddr156']['clock_hz']

    @property
    def control_hz(self):
        return self.h2d_clock_hz/self.design.architecture['control_semantics']['scheduler_clock_divider']

    @property
    def inventory_mode(self):
        if self.engine == 'rf':
            return 'rf_' + self.direction
        return 'wired' if self.wired_pad_path == 'serial' else 'usb'

    def record(self):
        result = dict(self.design.provenance(), engine=self.engine, direction=self.direction,
                      clock_source=self.clock_source, reference_hz=self.reference_hz,
                      clock_domains=self.clock_domains,
                      host_divider=self.host_divider, host_word_hz=self.host_word_hz,
                      h2d_word_hz=self.h2d_word_hz,h2d_clock_hz=self.h2d_clock_hz,control_hz=self.control_hz,
                      host_clock_source=self.host_clock_source,host_input_hz=self.host_input_hz,
                      inventory_mode=self.inventory_mode)
        if self.engine == 'rf':
            result.update(sample_divider=self.sample_divider, sample_hz=self.sample_hz,
                          pga_gain_db=self.pga_gain_db,lna_gain_db=self.lna_gain_db)
            if self.direction=='tx':
                result.update(tx_gain=self.tx_gain,tx_gain_code=self.tx_gain_code,
                              resolved_tx_gain=self.resolved_tx_gain)
        else:
            result.update(line_rate_bps=self.line_rate_bps, wired_pad_path=self.wired_pad_path,
                          cdr_periodic_tracking=self.cdr_periodic_tracking)
        return result


@dataclass(frozen=True)
class PhysicalOverride:
    """A declared uncertainty experiment, never a selectable hardware setting."""
    parameter: str
    value: float
    reason: str

    def __post_init__(self):
        if self.parameter not in ('package_return_inductance_h', 'host_output_load_f', 'die_decoupling_esl_h'):
            raise ValueError('Unknown physical uncertainty; hardware settings belong in configure()')
        if (isinstance(self.value, bool) or not isinstance(self.value, (int, float))
                or not math.isfinite(self.value) or self.value < 0):
            raise ValueError('Physical uncertainty must be finite and nonnegative')
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError('Physical deviation requires a reason')


@dataclass(frozen=True)
class Scenario:
    """Packet stimuli and explicit physical deviations for supported adapters.

    Temperature controls thermal noise only; broader assumptions remain unsupported;
    unknown inputs fail instead of being accepted without affecting the model.
    """
    overrides: tuple = ()
    wanted_dbm: float | None = None
    blocker_dbm: float | None = None
    reference_peak_v: float | None = None
    assumptions: Mapping = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.assumptions,Mapping) or set(self.assumptions)-{'temperature_c'}:
            raise ValueError('Unsupported operating assumption')
        assumptions=dict(self.assumptions)
        if 'temperature_c' in assumptions:
            value=assumptions['temperature_c']
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=-273.15:
                raise ValueError('Finite temperature above absolute zero required')
        object.__setattr__(self,'assumptions',MappingProxyType(assumptions))
        for name in ('wanted_dbm','blocker_dbm','reference_peak_v'):
            value=getattr(self,name)
            if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float))
                                      or not math.isfinite(value)):
                raise ValueError('Scenario stimulus must be finite: '+name)
        if self.reference_peak_v is not None and self.reference_peak_v<=0:
            raise ValueError('Positive reference drive required')
        object.__setattr__(self, 'overrides', tuple(self.overrides))
        if any(not isinstance(item, PhysicalOverride) for item in self.overrides):
            raise TypeError('Scenario requires typed physical overrides')
        if len({item.parameter for item in self.overrides}) != len(self.overrides):
            raise ValueError('Duplicate physical uncertainty')

    def override(self, *, reason, **parameters):
        if not parameters:
            raise ValueError('At least one physical parameter required')
        changes = {item.parameter: item for item in self.overrides}
        changes.update({key: PhysicalOverride(key, value, reason) for key, value in parameters.items()})
        return Scenario(tuple(changes[key] for key in sorted(changes)),
                        self.wanted_dbm,self.blocker_dbm,self.reference_peak_v,dict(self.assumptions))

    def record(self):
        return [dict(kind='physical_uncertainty', parameter=item.parameter,
                     value=item.value, reason=item.reason) for item in self.overrides]

    def stimulus_record(self):
        return dict(wanted_dbm=self.wanted_dbm,blocker_dbm=self.blocker_dbm,
                    reference_peak_v=self.reference_peak_v)

    def operating_conditions(self,design):
        board=design.architecture['blocks']['board']['parameters']
        temperature=self.assumptions.get('temperature_c',board['nominal_temperature_c'])
        low,high=board['temperature_c']
        if not low<=temperature<=high:
            raise ValueError('Temperature outside the selected operating window')
        return dict(temperature_c=temperature,temperature_k=temperature+273.15,
                    scope='Temperature affects frontend and sampling thermal noise only; gain, delay, phase noise, leakage and current temperature coefficients are not modeled.')

    def electrical_options(self, design):
        options = dict(return_l=_required(design.architecture, 'blocks.power.parameters.shared_return_l_h'),
                       output_cap_f=_required(design.contract,
                           'physical_services.host_output.full_rate_external_load_target_f'))
        keys = dict(package_return_inductance_h='return_l', host_output_load_f='output_cap_f',die_decoupling_esl_h='die_esl')
        options.update({keys[item.parameter]: item.value for item in self.overrides})
        return options
