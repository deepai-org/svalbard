"""Fast mitigation comparison using existing RF waveforms and declared budgets.

Not an end-to-end chip qualification. Every desired failure is retained and
unimplemented clock, bridge, circuit and FPGA requirements remain explicit.
"""
import hashlib
import json
import math
from dataclasses import replace, asdict
from fractions import Fraction
from pathlib import Path
import sys

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'system_model/architecture_fast'))
import numpy as np
from behavioral import Assumptions, waveform_screen, power_budget, rf_receiver_electrical_budget
from protocol_signals import fixture, gfsk, lora
from resource_configuration import validate_rf_settings
from oscillator_noise import PhaseNoise, loaded_clock_input_phase
from wired_envelope import wired_operating_envelopes, causal_receiver_envelope, wired_resource_requirements
from ble_packet import campaign as ble_packet_campaign


def write_evidence(path, result):
    """Atomic JSON snapshot; keep flat records compact without discarding data."""
    def encode(value, level=0):
        children=value.values() if isinstance(value,dict) else value
        if (not isinstance(value,(dict,list)) or not value or
                all(not isinstance(x,(dict,list)) for x in children)):
            return json.dumps(value,allow_nan=False,separators=(',', ':'))
        pad='  '*(level+1);close='  '*level
        if isinstance(value,dict):
            body=(pad+json.dumps(k)+': '+encode(v,level+1) for k,v in value.items())
            return '{\n'+',\n'.join(body)+'\n'+close+'}'
        return '[\n'+',\n'.join(pad+encode(v,level+1) for v in value)+'\n'+close+']'
    serialized=encode(result)+'\n'
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(serialized)
    temporary.replace(path)


# Assigned simultaneous impairment sets, not independent measured GF180 corners.
CASES = {
    'historical_optimistic': dict(converter_enob=9., relative_lo_phase_rms_rad=.03,
                                  frontend_evm_rms=.04),
    'moderate_precision': dict(converter_enob=8., relative_lo_phase_rms_rad=.015,
                               frontend_evm_rms=.04),
    'adverse_precision_noise': dict(converter_enob=6., relative_lo_phase_rms_rad=.06,
                                    frontend_evm_rms=.10),
}
LO_HZ = (2.4e9, 2.437e9, 2.484e9)


def board_die_transfer(frequency_hz, *, feed_r=2., feed_l=2e-9,
                       package_r=.1, package_l=2e-9, die_c=100e-12,
                       board_c=0., board_esr=.05, board_esl=1e-9,
                       die_esr=0., die_esl=0.):
    """Two-node small-signal PDN, host current at board node, victim at die.

    Board capacitor is outside the package, including ESR/ESL. Positive load
    current gives negative voltage. Returns complex transimpedance and KCL
    residual for a one-ampere test input; no fitted isolation multiplier.
    """
    values=(frequency_hz,feed_r,feed_l,package_r,package_l,die_c,board_c,board_esr,board_esl,die_esr,die_esl)
    if not all(math.isfinite(x) and x>=0 for x in values) or min(frequency_hz,feed_r,package_r,die_c)<=0:
        raise ValueError('Finite passive PDN and positive frequency required')
    w=2*math.pi*frequency_hz
    ys=1/(feed_r+1j*w*feed_l);yp=1/(package_r+1j*w*package_l)
    yb=0j if board_c==0 else 1/(board_esr+1j*w*board_esl+1/(1j*w*board_c))
    yd=1/(die_esr+1j*w*die_esl+1/(1j*w*die_c))
    matrix=np.array([[ys+yb+yp,-yp],[-yp,yp+yd]],complex)
    solution=np.linalg.solve(matrix,np.array([-1.,0.]))
    return dict(board_ohm=complex(solution[0]),die_ohm=complex(solution[1]),
                kcl_residual_a=float(max(abs(matrix@solution-np.array([-1.,0.])))))


def shared_return_transfer(frequency_hz, *, return_r=.1, return_l=2e-9,
                          shared_fraction=1., injection_weights=None, **network):
    """Three-node board supply / die supply / die return network.

    On-die decoupling connects die supply to die return; board decoupling goes
    to the ideal board return. The specified fraction of host current returns
    through the victim return impedance. Solve together, not by subtracting an
    independently calculated ground bounce from a fixed supply waveform.
    """
    if (not all(math.isfinite(v) for v in (return_r,return_l,shared_fraction))
            or return_r<0 or return_l<0 or not 0<=shared_fraction<=1):
        raise ValueError('Passive finite return and bounded sharing required')
    if injection_weights is not None and (len(injection_weights)!=3 or not all(math.isfinite(x) for x in injection_weights)):
        raise ValueError('Three finite normalized node-current weights required')
    if injection_weights is not None and return_r==0 and return_l==0:
        raise ValueError('Explicit current ports require a finite return impedance')
    # Reuse validation of the supply network and its ideal-return limit.
    baseline=board_die_transfer(frequency_hz,**network)
    if return_r==0 and return_l==0:
        return dict(differential_ohm=baseline['die_ohm'],ground_ohm=0j,
                    board_ohm=baseline['board_ohm'],die_ohm=baseline['die_ohm'],
                    kcl_residual_a=baseline['kcl_residual_a'],power_residual_w=0.)
    n=dict(feed_r=2.,feed_l=2e-9,package_r=.1,package_l=2e-9,
           die_c=100e-12,board_c=0.,board_esr=.05,board_esl=1e-9,die_esr=0.,die_esl=0.)
    n.update(network);w=2*math.pi*frequency_hz
    ys=1/(n['feed_r']+1j*w*n['feed_l'])
    yp=1/(n['package_r']+1j*w*n['package_l'])
    yg=1/(return_r+1j*w*return_l)
    yd=1/(n['die_esr']+1j*w*n['die_esl']+1/(1j*w*n['die_c']))
    yb=0j if n['board_c']==0 else 1/(n['board_esr']+1j*w*n['board_esl']+1/(1j*w*n['board_c']))
    matrix=np.array([[ys+yb+yp,-yp,0],[-yp,yp+yd,-yd],[0,-yd,yg+yd]],complex)
    injection=np.array([-1.,0.,shared_fraction] if injection_weights is None else injection_weights)
    vb,vd,vg=np.linalg.solve(matrix,injection)
    supplied=float(np.real(np.vdot(injection,[vb,vd,vg]))/2)
    loss=(abs(vb)**2*(ys.real+yb.real)+abs(vb-vd)**2*yp.real+abs(vg)**2*yg.real+abs(vd-vg)**2*yd.real)/2
    return dict(differential_ohm=complex(vd-vg),ground_ohm=complex(vg),
                board_ohm=complex(vb),die_ohm=complex(vd),
                kcl_residual_a=float(max(abs(matrix@np.array([vb,vd,vg])-injection))),
                power_residual_w=float(supplied-loss))


def return_pdn_scenarios(word_hz):
    base=next(r for r in host_pdn_scenarios(word_hz) if r['name']=='board_10uf_damped')
    rows=[]
    for label,r,l in [('ideal_return',0.,0.),('shared_return',.1,2e-9),
                      ('lower_impedance_return',.02,.5e-9)]:
        transfer=shared_return_transfer(1e6,return_r=r,return_l=l,**base['network'])
        voltage=base['host_current_tone_peak_a']*transfer['differential_ohm']
        ground=base['host_current_tone_peak_a']*transfer['ground_ohm']
        rows.append(dict(base,name=label,die_ripple_peak_v=abs(voltage),
            die_ripple_phase_rad=math.atan2(voltage.imag,voltage.real),
            return_r_ohm=r,return_l_h=l,shared_host_return_fraction=1.,
            ground_peak_v=abs(ground),ground_phase_rad=math.atan2(ground.imag,ground.real),
            dc_victim_rail_v=base['dc_victim_rail_v']-r*(base['host_data_average_a']+
                base['host_clock_average_a']+base['assumed_victim_dc_current_a']),
            kcl_residual_a=transfer['kcl_residual_a'],power_residual_w=transfer['power_residual_w'],
            scope='Joined supply/return network with full shared host return; substrate and signal-ground conversion remain separate unknowns.'))
    return rows


def host_pdn_scenarios(word_hz=2.437e9/8):
    """Declared activity envelope and component scenarios, not package data."""
    data_average=10*.25*word_hz*10e-12*3.3
    clock_average=.5*word_hz*10e-12*3.3
    # A sinusoidal 50% modulation of data activity at 1 MHz; not toggling at
    # 1 MHz in place of the fast host clock. Clock current stays in DC burden.
    peak=.5*data_average
    rows=[]
    for name,cap,series_r in [('no_board_cap',0.,.1),('board_100nf',100e-9,.1),
                             ('board_1uf',1e-6,.1),('board_1uf_damped',1e-6,2.),
                             ('board_10uf_damped',10e-6,2.)]:
        network=dict(feed_r=2.,feed_l=2e-9,package_r=.1,package_l=2e-9,
                     die_c=100e-12,board_c=cap,board_esr=.05,board_esl=1e-9)
        network['package_r']=series_r  # Includes optional external series damping.
        transfer=board_die_transfer(1e6,**network)
        voltage=peak*transfer['die_ohm']
        sweep=[(float(f),abs(board_die_transfer(float(f),**network)['die_ohm']))
               for f in np.geomspace(1e4,1e9,501)]
        maximum=max(sweep,key=lambda x:x[1])
        rows.append(dict(name=name,network=network,frequency_hz=1e6,host_word_rate_hz=word_hz,
            host_data_average_a=data_average,host_clock_average_a=clock_average,
            host_current_tone_peak_a=peak,die_ripple_peak_v=abs(voltage),
            die_ripple_phase_rad=math.atan2(voltage.imag,voltage.real),
            kcl_residual_a=transfer['kcl_residual_a'],
            frequency_scan_peak=dict(frequency_hz=maximum[0],transimpedance_ohm=maximum[1]),
            ideal_die_cap_plate_area_um2=100e-12/2e-15,
            dc_host_feed_drop_v=2*(data_average+clock_average),
            assumed_victim_dc_current_a=.024,
            dc_victim_rail_v=3.3-2*(data_average+clock_average+.024)-series_r*.024,
            local_series_resistor_dissipation_w=series_r*.024**2,
            scope='Host shared-board-feed path and assigned 24 mA victim DC load; common return, substrate, victim switching and real host spectrum remain unmodeled.'))
    return rows


def external_settings(settings, lo_hz, *, minimum_filter_samples=None):
    """Keep the same integer decimation tier; no hidden independent reference."""
    divider = int(64 * 40e6 / settings['sample_hz'])
    if minimum_filter_samples is not None:
        if not math.isfinite(minimum_filter_samples) or minimum_filter_samples<2:
            raise ValueError('Finite filter sampling margin of at least two required')
        # Generic filter/rate relationship; no knowledge of a radio protocol.
        while divider>64 and lo_hz/divider<minimum_filter_samples*settings['rx_cutoff_hz']:
            divider//=2
    rate = lo_hz / divider
    candidate = dict(settings, sample_hz=rate,
                     tx_cutoff_hz=min(settings['tx_cutoff_hz'], rate / 2),
                     sample_clock_source='external_lo', lo_hz=lo_hz,
                     lo_divider=divider)
    return validate_rf_settings(**candidate)


def clock_host_candidate(settings, contract):
    """Proposed all-integer chip clock tree; rate arithmetic, not edge proof.

    RF LO -> /16 D2H clock -> DDR gives LO/8 host words/s. ADC/DAC use
    LO/(64,128,256,512). H2D uses the existing external FPGA 156.25 MHz clock.
    Production pacing can then count D2H edges with a rational sample ratio;
    finite transport/pacing/recovery implementation is still unverified here.
    """
    lo = settings['lo_hz']
    divider = settings['lo_divider']
    t = contract['transport']
    payload = t['frame_words'] - t['control_words']
    d2h_clock = lo / 16
    d2h_word = 2 * d2h_clock
    h2d = t['profiles']['ddr156']
    h2d_word = h2d['clock_hz'] * h2d['edges']
    bits = 2 * settings['converter_bits']
    demand = bits * settings['sample_hz']
    cap = dict(d2h=d2h_word * t['word_bits'] * payload / t['frame_words'],
               h2d=h2d_word * t['word_bits'] * payload / t['frame_words'])
    return dict(d2h_clock_hz=d2h_clock, h2d_clock_hz=h2d['clock_hz'],
                divider_from_lo_to_d2h_clock=16,
                sample_per_d2h_word_ratio=[8, divider],
                demand_bps_per_active_direction=demand,
                capacity_bps_per_direction=cap,
                utilization={k: demand / v for k, v in cap.items()},
                within_existing_maximum_gpio_rate=d2h_clock <= h2d['clock_hz'],
                capacity_pass=all(demand < v for v in cap.values()),
                extra_signal_pins=0,
                new_clock_routes=['LO divider -> D2H clock', 'LO divider -> ADC/DAC'],
                unverified=['continuous host-clock settings and physical GPIO timing',
                            'finite paced TX bridge and clock loss/rearm',
                            'divider startup, quadrature and correlated phase/sample errors'])


def resampler_cost(wave_hz, converter_hz, *, taps=64, component_bits=18,
                   mac_clock_hz=200e6):
    # One real coefficient applies independently to I and Q. These are direct
    # form ceilings, not a synthesized/polyphase-optimized FPGA implementation.
    tx_macs = 2 * taps * converter_hz
    rx_macs = 2 * taps * wave_hz
    return dict(owner='external_fpga', on_chip_storage_bits=0,
                history_bits_per_direction=taps * 2 * component_bits,
                tx_real_macs_per_second=tx_macs, rx_real_macs_per_second=rx_macs,
                assumed_mac_clock_hz=mac_clock_hz,
                minimum_parallel_macs_at_assumed_clock=dict(
                    tx=math.ceil(tx_macs/mac_clock_hz), rx=math.ceil(rx_macs/mac_clock_hz)),
                tx_latency_s=(taps/2)/wave_hz,
                rx_lookahead_s=(taps/2)/converter_hz,
                additional_costs_unestimated=['coefficient generation or phase table',
                    'accumulators, pipeline state and numerical precision',
                    'transport buffering, timing recovery and modem'],
                throughput_implemented=False)


def make_wave(case, seed):
    if case['fixture'] == 'proprietary_gfsk':
        return gfsk(np.random.default_rng(seed).integers(0, 2, 64),
                    rate=case['symbol_rate_hz'])
    if case['fixture'] == 'lora_24':
        return lora(np.random.default_rng(seed).integers(0, 128, 8),
                    bandwidth=case['bandwidth_hz'])
    return fixture(case['fixture'], case.get('variant', ''), seed=seed)


def summarize_quality(q):
    eq = q['equalized']
    return dict(evm_rms=eq['evm_rms'] if eq and eq['acquired'] else q['evm_rms'],
                symbol_errors=eq['symbol_errors'] if eq and eq['acquired'] else q['symbol_errors'],
                dac_clipped_samples=q['dac_clipped_samples'],
                adc_clipped_samples=q['adc_clipped_samples'],
                acquisition=q['timing_recovery']['acquired'],
                carrier_acquired=q['carrier_recovery']['acquired'],
                conditional_waveform_pass=q['conditional_screen_pass'] and
                    q['dac_clipped_samples']==0 and q['adc_clipped_samples']==0)


def spectral_rf_mitigations(contract, seed_offsets=(0,100,200), mixer_substeps=4, pdn_scenarios=None, residual_pushing_hz_per_v=10e6, explicit_frontend=False, pga_peak_limit_v=.8, restore_gain=True, pga_gain_override=None, rf_rail_v=3.25, clock_names=None):
    """Joined RX clock/filter/blocker/supply scenarios; no device claims."""
    if not math.isfinite(rf_rail_v) or rf_rail_v<=0:raise ValueError('Finite positive RF rail required')
    base=next(c['rf'] for c in contract['behavioral_configuration_cases']
              if c['id']=='wifi_he20__40000000.0')
    carrier=2.437e9;band=(1e3,8e6)
    recipes=[('external_clean',None,-115.,-145.),
             ('external_noisy',None,-80.,-125.),
             ('autonomous_narrow',1e4,-80.,-145.),
             ('autonomous_wider',1e6,-80.,-145.)]
    if clock_names is not None:
        if not clock_names or not set(clock_names)<={r[0] for r in recipes}:raise ValueError('Known clock scenarios required')
        recipes=[r for r in recipes if r[0] in clock_names]
    results=[]
    for (name,pole,colored,floor),seed_offset in [(r,s) for r in recipes for s in seed_offsets]:
        settings=(base if pole else external_settings(base,carrier))
        source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=colored,floor_dbc_hz=floor,
            offset_band_hz=band,loop_pole_hz=pole or 0.,injection='vco' if pole else 'direct',seed=831+seed_offset)
        if pole:
            source=source.plus(PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-250.,
                floor_dbc_hz=-130.,offset_band_hz=band,loop_pole_hz=pole,
                injection='reference',seed=832+seed_offset))
        # Three independent additive stages, 0.3 ps each over this SAME band.
        stage_floor=10*math.log10((2*math.pi*carrier*.3e-12)**2/(2*(band[1]-band[0])))
        common=source.plus(PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-250.,
            floor_dbc_hz=stage_floor,offset_band_hz=band,seed=833+seed_offset))
        branch=PhaseNoise(())
        for seed in (834,835):
            branch=branch.plus(PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-250.,
                floor_dbc_hz=stage_floor,offset_band_hz=band,seed=seed+seed_offset))
        selected_pdn=(pdn_scenarios.get('autonomous' if pole else 'external')
                      if isinstance(pdn_scenarios,dict) else pdn_scenarios)
        disturbances=(selected_pdn if pdn_scenarios is not None else
            [dict(name='assigned',die_ripple_peak_v=v,die_ripple_phase_rad=0.) for v in (.010,.001)])
        for disturbance in disturbances:
            ripple=disturbance['die_ripple_peak_v']
            # Assigned POST-loop residual frequency pushing at 1 MHz. For a
            # sinusoidal frequency disturbance, phase peak = K*Vpeak/f_offset.
            # Shared path before phase/sample branching; no independent RSS.
            # Integral of cosine frequency modulation gives sine phase.
            spur_phase=(disturbance['die_ripple_phase_rad']-math.pi/2
                        if pdn_scenarios is not None else 0.)
            spur=PhaseNoise(((1e6,residual_pushing_hz_per_v*ripple/1e6,spur_phase),))
            sample_phase=common.plus(spur)
            mixer=sample_phase.plus(branch)
            for attenuation in (0.,20.):
                loss=0. if attenuation==0 else 2.
                a=replace(Assumptions(),converter_enob=8.,relative_lo_phase_rms_rad=0.,
                    sample_jitter_s=.3e-12,frontend_evm_rms=.04 if explicit_frontend else .04*10**(loss/20))
                actual_settings=dict(settings)
                if explicit_frontend and restore_gain:
                    actual_settings['rx_gain']*=10**(loss/20)
                if pga_gain_override is not None:
                    if not explicit_frontend or restore_gain:raise ValueError('Explicit gain override requires un-restored frontend')
                    actual_settings['rx_gain']=pga_gain_override
                q=waveform_screen(fixture('wifi_he20',seed=81),a,
                    {'estimated_rail_v':{'RF':rf_rail_v}},settings=actual_settings,
                    recover_carrier=True,fpga_resampling=True,
                    blocker=dict(offset_hz=12e6,relative_power_db=20.-attenuation+loss),
                    frontend_saturation_v=2.,mixer_phase_noise=mixer,
                    sample_phase_noise=sample_phase if pole is None else None,
                    mixer_substeps=mixer_substeps,frontend_loss_db=loss if explicit_frontend else 0.,
                    pga_peak_limit_v=pga_peak_limit_v if explicit_frontend else None)
                results.append(dict(rf_rail_v=rf_rail_v,clock=name,seed_offset=seed_offset,pll_pole_hz=pole,
                    source_colored_100khz_dbc_hz=colored,source_floor_dbc_hz=floor,
                    offset_band_hz=list(band),post_loop_pushing_hz_per_v=residual_pushing_hz_per_v,
                    rail_ripple_peak_v=ripple,disturbance=disturbance['name'],board_blocker_attenuation_db=attenuation,
                    board_wanted_insertion_loss_db=loss,
                    residual_blocker_relative_db=20.-attenuation+loss,
                    quality=summarize_quality(q),spectral_clock=q['spectral_clock'],
                    compression=q['frontend_compression'],pga_headroom=q['pga_headroom']))
    return dict(status='joined_conditional_receive_waveform_screen',cases=results,
        seed_offsets=list(seed_offsets),mixer_substeps=mixer_substeps,
        assumptions=['Declared finite PSD realizations, 96 logarithmic lines per source; a few seeds do not establish statistics or silicon yield.',
          'Stimulus source DAC has independent ideal timing; local receive mixer gets phase before filtering.',
          'Direct-LO common phase also perturbs ADC timestamps with its signed first-order crossing error.',
          'Autonomous converter remains reference-derived; its aperture error is separately assigned.',
          'Board filter loss increases input-referred noise; wanted amplitude restored by assumed gain headroom.',
          ('Supply ripple is assigned after filtering/PLL rejection, not predicted by a joined host/PDN network.' if pdn_scenarios is None else
           'Supply ripple phasor comes from host activity current through a two-node board/package network; post-loop pushing remains assigned.'),
          'Compression is the existing radial envelope model; no two-tone IIP3 or blocker mask qualification.',
          'Fixed 10% diagnostic EVM threshold is not a protocol standard.'],
        remaining=['further spectral/analog-time refinement and statistical confidence beyond the retained checks',
          'measured or circuit-derived spectra, actual PLL transfer and supply rejection',
          'gain/headroom/power cost of insertion-loss compensation',
          'independent remote clock drift and protocol acquisition',
          'complete TX path and connected host/PDN/area/observability'])


def spectral_suite(contract):
    result=spectral_rf_mitigations(contract)
    coarse=[r for r in result['cases'] if r['seed_offset']==0]
    fine=spectral_rf_mitigations(contract,seed_offsets=(0,),mixer_substeps=8)['cases']
    comparisons=[]
    for a,b in zip(coarse,fine):
        key=('clock','seed_offset','rail_ripple_peak_v','board_blocker_attenuation_db')
        if any(a[k]!=b[k] for k in key):raise AssertionError('Refinement case mismatch')
        comparisons.append(dict(**{k:a[k] for k in key},
            evm_4=a['quality']['evm_rms'],evm_8=b['quality']['evm_rms'],
            acceptance_unchanged=a['quality']['conditional_waveform_pass']==b['quality']['conditional_waveform_pass']))
    result['time_grid_refinement']=dict(cases=comparisons,
        maximum_absolute_evm_change=max(abs(r['evm_4']-r['evm_8']) for r in comparisons),
        acceptance_unchanged=all(r['acceptance_unchanged'] for r in comparisons),
        scope='One spectral seed, four to eight mixer/filter substeps per ADC period; not full convergence or nonlinear alias qualification.')
    return result


def explicit_gain_suite(contract):
    networks={mode:[next(r for r in return_pdn_scenarios(rate)
                         if r['name']=='lower_impedance_return')]
              for mode,rate in [('external',2.437e9/8),('autonomous',250e6)]}
    cases=[]
    for gain,limit,override in [(False,.8,None),(True,.8,None),(True,.35,None),(False,.35,.5)]:
        result=spectral_rf_mitigations(contract,seed_offsets=(0,),pdn_scenarios=networks,
            residual_pushing_hz_per_v=65e6,explicit_frontend=True,
            pga_peak_limit_v=limit,restore_gain=gain,pga_gain_override=override)
        for row in result['cases']:
            if row['board_blocker_attenuation_db']==20:
                cases.append(dict(row,restore_gain=gain,
                    sampled_output_current_lower_bound_a_per_1pf=
                    row['pga_headroom']['sampled_slew_lower_bound_v_per_s']*1e-12))
    return dict(status='explicit_loss_gain_and_signal_headroom_candidate',cases=cases,
        ordering='Board loss -> mixer/compression -> RX filter -> configured PGA -> signal headroom -> noise -> ADC.',
        assumptions=['Same lower-return-impedance, 10 uF damped network and 65 MHz/V stress as shared-return comparison.',
            '2 dB wanted loss is applied to voltage; fixed receiver noise is not attenuated with the signal.',
            'Restoration consumes gain 1.2589 within the existing 0.5–2 range, not an invisible amplitude boost.',
            '0.8/0.35 V per-component signal limits are assigned PGA hypotheses; noise excursions are not clipped at that stage.',
            'Sampled slew*C is only a drive-current lower bound; total PGA bias, bandwidth, noise and area remain unestimated.'],
        remaining=['continuous-time and noisy headroom','reference/common-mode variation',
                   'physical gain setting, bandwidth and current','full-chain power/area and diagnostic discrimination'])


def diagnostic_observability_suite(contract):
    """Bench intervention signatures using digitized outputs only.

    Hypothesis labels select injected conditions, never input to inference.
    Bounded interval separation is not a classifier or statistical confidence.
    """
    base=next(c['rf'] for c in contract['behavioral_configuration_cases']
              if c['id']=='wifi_he20__40000000.0')
    settings=external_settings(base,2.437e9)
    hypotheses={
        'nominal':[(8.,.04,.8,-115.),(8.,.05,.8,-110.)],
        'source_phase':[(8.,.04,.8,-85.),(8.,.04,.8,-80.)],
        'pga_headroom':[(8.,.04,.3,-115.),(8.,.04,.4,-115.)],
        'converter_noise':[(5.,.04,.8,-115.),(6.,.04,.8,-115.)],
        # Deliberate identifiability control: the present model observes the
        # same equivalent white noise after PGA regardless of which physical
        # sampling/conversion element produced it. Do not invent a diagnosis.
        'post_pga_sampler_noise':[(5.,.04,.8,-115.),(6.,.04,.8,-115.)],
        'frontend_noise':[(8.,.12,.8,-115.),(8.,.18,.8,-115.)]}
    interventions={'baseline':(1.,False),'low_gain':(.5,False),
                   'high_gain':(1.5,False),'clean_external_source':(1.,True)}
    rows=[]
    for name,parameters in hypotheses.items():
        for corner,(enob,front,limit,colored) in enumerate(parameters):
            for seed in (81,109):
                observations={}
                for intervention,(gain,clean) in interventions.items():
                    phase=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-120. if clean else colored,
                        floor_dbc_hz=-145.,seed=seed)
                    a=replace(Assumptions(),converter_enob=enob,frontend_evm_rms=front,
                              relative_lo_phase_rms_rad=0.,sample_jitter_s=.3e-12)
                    q=waveform_screen(fixture('wifi_he20',seed=seed),a,
                        {'estimated_rail_v':{'RF':3.25}},settings=dict(settings,rx_gain=gain),
                        fpga_resampling=True,recover_carrier=True,mixer_phase_noise=phase,
                        sample_phase_noise=phase,mixer_substeps=4,pga_peak_limit_v=limit)
                    quality=summarize_quality(q)
                    # Deliberately exclude model-only PGA clipping, true ADC
                    # clipping count, injected noise and internal node values.
                    observations[intervention]=dict(evm_rms=quality['evm_rms'],
                        digitized_rms=q['raw_received_rms_v'],acquired=quality['acquisition'] and quality['carrier_acquired'])
                rows.append(dict(injected_hypothesis=name,corner=corner,seed=seed,
                                 observations=observations))
    features={}
    for name in hypotheses:
        selected=[r for r in rows if r['injected_hypothesis']==name]
        if any(not o['acquired'] for r in selected for o in r['observations'].values()):
            raise ValueError('Diagnostic acquisition failed; EVM intervals are not valid observables')
        values={k:[r['observations'][k]['evm_rms'] for r in selected] for k in interventions}
        for k in ('low_gain','high_gain','clean_external_source'):
            values[k+'_delta']=[r['observations'][k]['evm_rms']-
                               r['observations']['baseline']['evm_rms'] for r in selected]
        features[name]={k:[min(v),max(v)] for k,v in values.items()}
    pairs=[]
    names=list(hypotheses)
    for i,name in enumerate(names):
        for other in names[i+1:]:
            gaps={}
            for feature in features[name]:
                a,b=features[name][feature],features[other][feature]
                gaps[feature]=max(b[0]-a[1],a[0]-b[1])
            witness=max(gaps,key=gaps.get)
            pairs.append(dict(hypotheses=[name,other],largest_interval_gap=gaps[witness],
                baseline_only_separated=gaps['baseline']>.01,
                separating_feature=witness if gaps[witness]>.01 else None,
                separated_in_this_sweep=gaps[witness]>.01))
    return dict(status='conditional_diagnostic_identifiability_screen',observations=rows,
        feature_intervals=features,pairwise_discrimination=pairs,
        minimum_required_interval_gap_evm=.01,
        controls='Existing PGA settings and stopped replacement of external LO at unchanged carrier/rate; external FPGA generates known stimulus and analyzes digitized samples.',
        intentional_alias='Converter-core and post-PGA sampler equivalent white noise share the same observable transfer in this model; report the aggregate noise location, not a unique physical source.',
        additional_chip_storage_bits=0,additional_pins=0,
        limitations=['Two severity settings and two seeds per hypothesis, not a measured population.',
            'Gain sweep can itself cause clipping; all resulting observations are retained.',
            'Clean-source intervention replaces only modeled source phase, not real distribution/supply/reference errors.',
            'No internal fault label, true clipping flag or hidden analog waveform used as an observable.',
            'Overlapping intervals remain ambiguous; mixed faults and unmodeled distortions can invalidate discrimination.',
            'External stimulus/source quality, gain calibration and monitor precision must be established.',
            'Stage-selective bypass, reference diagnosis, wired diagnosis and lifecycle remain unverified.'])


def host_pdn_suite(contract):
    networks=dict(external=host_pdn_scenarios(),autonomous=host_pdn_scenarios(250e6))
    result=spectral_rf_mitigations(contract,seed_offsets=(0,),pdn_scenarios=networks)
    stress=spectral_rf_mitigations(contract,seed_offsets=(0,),pdn_scenarios=networks,
                                   residual_pushing_hz_per_v=65e6)
    result['cases'].extend(stress['cases'])
    result['networks']=networks
    result['status']='conditional_host_activity_to_clock_phase_to_receive_quality'
    result['cost_and_coverage']={
        'additional_pins':0,'on_die_capacitance_per_victim_domain_f':100e-12,
        'ideal_plate_area_at_2ff_per_um2':50000.,
        'area_ownership':'Must fit existing timing allocation; not an extracted or placed area claim.',
        'external_parts':'0 / 100 nF / 1 uF / 10 uF effective board capacitance, optional series damping; ESR/ESL included. Effective capacitance under bias, not nominal part markings.',
        'insertion_loss_compensation':'2 dB extra gain remains assumed; its noise/current/headroom implementation is open.',
        'excluded':'Shared ground, substrate, supply-current edge spectra, victim switching, regulators, multi-domain dynamics, startup and thermal behavior.',
        'high_frequency_scan':'Lumped-network sensitivity only, not package characterization. Peaks do not establish RF failure without coupling/filter/alias analysis.'}
    return result


def shared_return_suite(contract):
    networks=dict(external=return_pdn_scenarios(2.437e9/8),
                  autonomous=return_pdn_scenarios(250e6))
    result=spectral_rf_mitigations(contract,seed_offsets=(0,),pdn_scenarios=networks,
                                   residual_pushing_hz_per_v=65e6)
    result['networks']=networks
    result['status']='conditional_joined_supply_and_return_coupling'
    result['limitations']=[
        'All networks retain the 10 uF board capacitor and 2 ohm series damping.',
        'Lower return impedance is a routing/package requirement, not an achieved assembly measurement.',
        'No extra ground pin assumed; existing separate host/PLL returns must actually provide the required transfer.',
        'Ground motion also affects signal common mode, input threshold and reference levels; only differential-supply clock pushing is propagated here.',
        'One spectral seed and 1 MHz host activity tone; not a full switching or substrate model.',
        'No die-fit, complete power or protocol-qualification claim.']
    return result


def tx_spectral_suite():
    """Actual loaded DAC/filter/driver waveform plus assigned independent LO.

    Baseline-relative EVM isolates added clock error, not total demodulated EVM.
    Windowed channel-power ratios are diagnostics, not an emission mask test.
    """
    from behavioral import tx_ofdm_crest_screen, rf_tx_compliance_budget
    rows=[];carrier=2.437e9;band=(1e3,8e6)
    for voltage_scale in (5.02,4.5):
        captures=[]
        driver=tx_ofdm_crest_screen((953,977),tx_voltage_scale=voltage_scale,source_resistance_ohm=40.,
            peak_current_limit_a=.028,capture=captures,interpolation='fir')
        for capture,cost in zip(captures,driver['cases']):
            t=capture['times_s'];baseline=capture['loaded_voltage']
            fs=1/float(np.median(np.diff(t)));freq=np.fft.fftfreq(len(t),1/fs)
            window=np.hanning(len(t))
            def spectrum(z):
                power=abs(np.fft.fft(z*window))**2
                center=float(np.sum(power[abs(freq)<10e6]))
                adjacent=float(np.sum(power[(abs(freq)>=10e6)&(abs(freq)<30e6)]))
                return adjacent/center
            base_ratio=spectrum(baseline)
            compliance=rf_tx_compliance_budget(peak_open_v=cost['peak_current_a']*90.,
                minimum_supply_v=3.144,total_rail_bias_a=.037,source_resistance_ohm=40.,
                load_resistance_ohm=50.,driver_bias_current_a=.028,peak_current_limit_a=.028,
                headroom_per_rail_v=.3,differential=True)
            for name,pole,colored,floor in [('external_clean',0.,-115.,-145.),
                                           ('external_noisy',0.,-80.,-125.),
                                           ('autonomous_wider',1e6,-80.,-145.)]:
                phase=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=colored,floor_dbc_hz=floor,
                    offset_band_hz=band,loop_pole_hz=pole,injection='vco' if pole else 'direct',seed=831)
                if pole:
                    phase=phase.plus(PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-250.,
                        floor_dbc_hz=-130.,offset_band_hz=band,loop_pole_hz=pole,injection='reference',seed=832))
                stage_floor=10*math.log10((2*math.pi*carrier*.3e-12)**2/(2*(band[1]-band[0])))
                for seed in (833,834,835):
                    phase=phase.plus(PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-250.,
                        floor_dbc_hz=stage_floor,offset_band_hz=band,seed=seed))
                for ripple in (0.,.001,.01):
                    # Assigned residual pushing after any rejection; phase/FM
                    # integration, not a second ideal PLL suppression factor.
                    phi=phase.phase(t)+65e6*ripple/1e6*np.sin(2*np.pi*1e6*t)
                    emitted=baseline*np.exp(1j*phi)
                    fitted=np.vdot(baseline,emitted)/np.vdot(baseline,baseline)
                    raw=float(np.linalg.norm(emitted-baseline)/np.linalg.norm(baseline))
                    residual=float(np.linalg.norm(emitted-fitted*baseline)/np.linalg.norm(baseline))
                    rows.append(dict(payload_seed=capture['payload_seed'],clock=name,tx_voltage_scale=voltage_scale,
                        residual_pushing_hz_per_v=65e6,rail_ripple_peak_v=ripple,
                        incremental_raw_evm_rms=raw,incremental_constant_fit_evm_rms=residual,
                        baseline_adjacent_to_channel_ratio=base_ratio,
                        emitted_adjacent_to_channel_ratio=spectrum(emitted),
                        average_load_power_w=cost['average_load_power_w'],
                        emitted_average_load_power_w=float(np.mean(abs(emitted)**2)/100),electrical=compliance))
    return dict(cases=rows,status='conditional_loaded_tx_spectral_screen',fir_cost=resampler_cost(20e6,40e6),
        scope=['Existing FPGA FIR interpolation, quantized DAC, reconstruction filter and nonlinear IQ driver; 40 ohm source into 50 ohm differential load.',
            'Uniform 40 MHz DAC timestamps; independent observer. No shared-LO cancellation. Source spectra assigned over 1 kHz–8 MHz offsets only.',
            'EVM compares emitted waveform to the same distorted baseline. Constant complex fit uses the full diagnostic record; not implemented receiver tracking or total packet EVM.',
            'Adjacent power is summed over both 10–30 MHz offset bands divided by central +/-10 MHz, using a Hann window. No regulatory or protocol mask claim.',
            'Ripple is an assigned residual clock modulation, not a joined TX-load PDN result. AM pushing, DAC jitter, PA supply response and wide-offset noise remain open.',
            'Output-gain reduction preserves the assigned normalized nonlinearity; physical gain/bias dependence is not modeled.',
            'Driver bias is included in 37 mA RF bias. Electrical bounds are assigned, not physical qualification; area and complete rail current remain unresolved.'])


def tx_image_attribution_suite():
    """Separate host interpolation images from declared output-stage errors."""
    from behavioral import tx_ofdm_crest_screen, rf_tx_compliance_budget
    rows=[]
    configurations=[(mode,ideal,10e6) for mode in ('repeat','fir') for ideal in (False,True)]
    configurations += [('fir',False,5e6),('fir',False,15e6)]
    for interpolation,ideal,cutoff in configurations:
        captures=[]
        report=tx_ofdm_crest_screen((953,977),tx_voltage_scale=4.5,
            source_resistance_ohm=40.,peak_current_limit_a=.028,capture=captures,
            interpolation=interpolation,ideal_output=ideal,tx_cutoff_hz=cutoff)
        for capture,cost in zip(captures,report['cases']):
            t=capture['times_s'];z=capture['loaded_voltage']
            fs=1/float(np.median(np.diff(t)));f=np.fft.fftfreq(len(t),1/fs)
            power=abs(np.fft.fft(z*np.hanning(len(z))))**2
            center=float(np.sum(power[abs(f)<10e6]))
            bands={name:float(np.sum(power[(abs(f)>=lo)&(abs(f)<hi)]))/center
                for name,lo,hi in [('adjacent_10_30mhz',10e6,30e6),('dac_image_30_50mhz',30e6,50e6)]}
            electrical=rf_tx_compliance_budget(peak_open_v=cost['peak_current_a']*90.,
                minimum_supply_v=3.144,total_rail_bias_a=.037,source_resistance_ohm=40.,
                load_resistance_ohm=50.,driver_bias_current_a=.028,peak_current_limit_a=.028,
                headroom_per_rail_v=.3,differential=True)
            rows.append(dict(interpolation=interpolation,ideal_output=ideal,tx_cutoff_hz=cutoff,
                reconstruction_gain_at_9mhz_db=-10*math.log10(1+(9e6/cutoff)**2),
                payload_seed=capture['payload_seed'],band_power_ratios=bands,
                average_load_power_w=cost['average_load_power_w'],dac_clips=cost['dac_clips'],
                electrical=electrical))
    for row in rows:
        reference=next(r for r in rows if r['tx_cutoff_hz']==10e6 and
            r['interpolation']==row['interpolation'] and r['ideal_output']==row['ideal_output'] and
            r['payload_seed']==row['payload_seed'])
        scale=math.sqrt(reference['average_load_power_w']/row['average_load_power_w'])
        row['same_average_power_requirement']=dict(voltage_multiplier=scale,
            required_open_peak_v=row['electrical']['peak_open_v']*scale,
            required_peak_current_a=row['electrical']['peak_load_current_a']*scale,
            scope='Linear gain requirement only; restoring average power does not undo frequency-dependent droop or establish EVM.')
    return dict(cases=rows,status='conditional_interpolation_image_attribution',
        fir_cost=resampler_cost(20e6,40e6),
        scope=['Same DAC rate, one-pole reconstruction topology, output gain and resistive load; explicit cutoff sweeps are configuration changes.',
            'FIR uses existing 64-tap centered reconstruction; FPGA needs 32 input-sample lookahead/delay and implementation resources. No extra chip pins or converter rate assumed.',
            'Ideal-output control removes only assigned IQ imbalance, feedthrough and cubic compression; it retains DAC and reconstruction.',
            'Band-power ratios sum both positive/negative offsets with a Hann window, not an emission-mask measurement.',
            'No extra analog filter added. FIR coefficient precision, FPGA scheduling, total demodulated EVM and emission compliance remain unverified.',
            'Fixed output gain: interpolation changes RMS and crests; electrical failures must not be hidden by independent power normalization.'])


def weak_rf_recipe_controls(contract):
    """Separate selected recipe distortion from removable random impairments."""
    idealized=replace(Assumptions(),converter_enob=12.,relative_lo_phase_rms_rad=0.,
        frontend_evm_rms=0.,sample_jitter_s=0.)
    rows=[]
    for case in contract['behavioral_configuration_cases']:
        if not case['id'].startswith(('bluetooth_le_2m','lora_24')):continue
        for lo in LO_HZ:
            settings=external_settings(case['rf'],lo)
            q=waveform_screen(make_wave(case,81),idealized,{'estimated_rail_v':{'RF':3.25}},
                settings=settings,recover_carrier=True,fpga_resampling=True)
            rows.append(dict(recipe=case['id'],lo_hz=lo,settings=settings,quality=summarize_quality(q)))
    comparisons=[]
    moderate=replace(Assumptions(),**CASES['moderate_precision'])
    for case in contract['behavioral_configuration_cases']:
        if not case['id'].startswith(('bluetooth_le_2m','lora_24')):continue
        for mode in ('baseline','wider_rx','first_order','faster_sampling'):
            for lo in LO_HZ:
                base=case['rf']
                settings=external_settings(dict(base,sample_hz=base['sample_hz']*2) if mode=='faster_sampling' else base,lo)
                if mode=='wider_rx':settings=validate_rf_settings(**dict(settings,rx_cutoff_hz=2*settings['rx_cutoff_hz']))
                if mode=='first_order':settings=validate_rf_settings(**dict(settings,rx_filter_order=1))
                blockers=[None]
                if case['fixture']=='bluetooth_le' and lo==2.437e9 and mode!='faster_sampling':
                    blockers.append(dict(offset_hz=4e6,relative_power_db=0.))
                for blocker in blockers:
                    q=waveform_screen(make_wave(case,81),moderate,{'estimated_rail_v':{'RF':3.25}},
                        settings=settings,recover_carrier=True,fpga_resampling=True,blocker=blocker)
                    comparisons.append(dict(recipe=case['id'],configuration_change=mode,lo_hz=lo,
                        settings=settings,blocker=blocker,quality=summarize_quality(q),
                        converter_rate_ratio_to_baseline=settings['sample_hz']/external_settings(base,lo)['sample_hz'],
                        ideal_rx_attenuation_at_twice_original_cutoff_db=10*math.log10(1+(2*base['rx_cutoff_hz']/settings['rx_cutoff_hz'])**(2*settings['rx_filter_order']))))
    return dict(cases=rows,assumptions=asdict(idealized),configuration_comparisons=comparisons,comparison_assumptions=asdict(moderate),
        scope=['Control removes assigned frontend white noise, IID LO phase noise and aperture jitter; ideal 12-bit quantization remains.',
            'Same existing preserve-tier filter/rate settings, FPGA interpolation and prefix acquisition; no payload-fitted equalizer.',
            'Residual EVM is not all transistor noise. A poor control points to waveform/filter/timing/receiver limitations before improving ENOB or clocks.',
            'This control is not a guaranteed lower bound: nonlinear interactions or a different configuration can change EVM.',
            'Generic 10% EVM acceptance is diagnostic, not a BLE or LoRa specification.',
            'Configuration comparisons change one setting at a time under moderate impairment assumptions. Wider filters sacrifice selectivity; doubled conversion rates increase converter/host work, with actual power unpriced.',
            'BLE blocker is an equal-power 4 MHz offset diagnostic, not a protocol interference test. No blocker compression or spectral LO coupling is added in this comparison.'])


def lora_recovery_suite(contract):
    """Diagnostic known-prefix estimator study, not a LoRa preamble model."""
    a=replace(Assumptions(),**CASES['moderate_precision']);rows=[]
    for case in contract['behavioral_configuration_cases']:
        if not case['id'].startswith('lora_24'):continue
        factors=(1.,2.) if case['bandwidth_hz']>500e3 else (1.,)
        for factor in factors:
            for lo in LO_HZ:
                base=external_settings(case['rf'],lo)
                settings=validate_rf_settings(**dict(base,rx_cutoff_hz=base['rx_cutoff_hz']*factor))
                for seed in (81,181):
                    for offset in (0.,5000.):
                        for count in (512,2048):
                            blockers=[None]
                            if case['bandwidth_hz']>500e3 and lo==2.437e9 and seed==81 and offset==5000. and count==2048:
                                blockers.append(dict(offset_hz=1.6e6,relative_power_db=0.))
                            for blocker in blockers:
                                # White input-noise density integrated by the same-order
                                # analog filter scales RMS with sqrt(cutoff).
                                # This is an explicit sensitivity assumption, not NF data.
                                case_a=replace(a,frontend_evm_rms=a.frontend_evm_rms*math.sqrt(factor))
                                q=waveform_screen(make_wave(case,seed),case_a,{'estimated_rail_v':{'RF':3.25}},
                                    settings=settings,seed=seed,recover_carrier=True,fpga_resampling=True,
                                    training_samples=count,carrier_offset_hz=offset,blocker=blocker)
                                estimate=q['carrier_recovery']['estimate_hz']
                                rows.append(dict(recipe=case['id'],lo_hz=lo,seed=seed,injected_offset_hz=offset,
                                    rx_cutoff_multiplier=factor,settings=settings,blocker=blocker,
                                    frontend_evm_rms=case_a.frontend_evm_rms,frontend_noise_variance_multiplier=factor,
                                    ideal_rx_attenuation_at_1_6mhz_db=10*math.log10(1+(1.6e6/settings['rx_cutoff_hz'])**(2*settings['rx_filter_order'])),
                                    training_samples=count,prefix_duration_s=count/settings['sample_hz'],
                                    diagnostic_fpga_buffer_bits=count*2*18,
                                    carrier_estimate_hz=estimate,estimation_error_hz=None if estimate is None else estimate-offset,
                                    timing_estimate=q['timing_recovery'],quality=summarize_quality(q)))
    return dict(cases=rows,assumptions=asdict(a),
        scope=['Converter rate is unchanged. Baseline and doubled RX cutoff are explicitly separated, with short/long synthetic prefixes. Diagnostic prefix shaping follows selected cutoff; not fixed standard-preamble evidence.',
            'Wider-band equal-power 1.6 MHz blocker controls retain zero compression and legacy IID phase assumptions; no complete RF interference claim.',
            'Frontend noise RMS scales with sqrt(cutoff multiplier) as an input-white-noise sensitivity model. Other converter/phase impairments remain fixed; actual noise spectra remain unknown.',
            'Frequency truth is used only to score estimation error, never to correct received samples.',
            'Full-buffer cost assumes external FPGA storage with 18-bit I/Q. Streaming sufficient-statistic implementations may need less but are unverified. No on-chip storage added.',
            'Longer prefix costs airtime and acquisition latency. This diagnostic prefix is not a standard LoRa preamble; results do not establish interoperability.',
            'Two seeded payload/noise realizations, three LO settings and zero/5 kHz offsets are a bounded study, not a statistical acquisition guarantee.'])


def rf_bench_diagnostics(study):
    """Bench-visible paired interventions, without injected frequency truth."""
    rows=study['cases'];pairs=[]
    def key(r):
        return (r['recipe'],r['lo_hz'],r['seed'],r['injected_offset_hz'],r['rx_cutoff_multiplier'])
    def visible(r):
        # No internal analog nodes, true clipping counters or error relative
        # to injected frequency are available to this observation record.
        return dict(known_stimulus_evm=r['quality']['evm_rms'],
            known_stimulus_symbol_errors=r['quality']['symbol_errors'],
            carrier_estimate_hz=r['carrier_estimate_hz'],
            acquired=r['quality']['acquisition'] and r['quality']['carrier_acquired'])
    for before in rows:
        if before['blocker'] is not None:continue
        choices=[]
        if before['training_samples']==512:
            choices += [('longer_training',r) for r in rows if key(r)==key(before) and
                r['training_samples']==2048 and r['blocker'] is None]
        if before['training_samples']==2048:
            choices += [('introduce_blocker',r) for r in rows if key(r)==key(before) and
                r['training_samples']==2048 and r['blocker'] is not None]
            if before['rx_cutoff_multiplier']==1:
                choices += [('wider_filter',r) for r in rows if key(r)[:-1]==key(before)[:-1] and
                    r['rx_cutoff_multiplier']==2 and r['training_samples']==2048 and r['blocker'] is None]
        for intervention,after in choices:
            first,last=visible(before),visible(after)
            pairs.append(dict(recipe=before['recipe'],lo_hz=before['lo_hz'],seed=before['seed'],
                intervention=intervention,rx_cutoff_multiplier_before=before['rx_cutoff_multiplier'],
                observations_before=first,observations_after=last,
                evm_change=last['known_stimulus_evm']-first['known_stimulus_evm'],
                carrier_estimate_change_hz=None if None in (first['carrier_estimate_hz'],last['carrier_estimate_hz']) else last['carrier_estimate_hz']-first['carrier_estimate_hz']))
    summaries=[]
    for recipe,intervention,factor in sorted({(r['recipe'],r['intervention'],r['rx_cutoff_multiplier_before']) for r in pairs}):
        selected=[r for r in pairs if (r['recipe'],r['intervention'],r['rx_cutoff_multiplier_before'])==(recipe,intervention,factor)]
        summaries.append(dict(recipe=recipe,intervention=intervention,rx_cutoff_multiplier_before=factor,
            evm_change_range=[min(r['evm_change'] for r in selected),max(r['evm_change'] for r in selected)],
            acquisition_lost_in_observed_pair=any(r['observations_before']['acquired'] and not r['observations_after']['acquired'] for r in selected)))
    return dict(paired_observations=pairs,intervention_signatures=summaries,
        status='bench_procedure_evidence_not_unique_fault_localization',
        required_access=['Existing RF input and host-returned I/Q samples; waveform/estimator processing and capture storage in external FPGA or lab host.',
            'Independent known RF stimulus with controlled carrier and blocker; shared-LO chip loopback alone can hide phase errors.',
            'Existing generic cutoff/rate configuration and controlled known-training waveforms; no new chip pins or internal analog probe assumed.'],
        ambiguities=['Longer training changes noise averaging and delay/gain fitting as well as carrier estimation; improvement alone does not identify oscillator phase noise.',
            'Filter widening changes selectivity, group delay, integrated noise and diagnostic prefix shaping; improvement does not identify a defective filter component.',
            'Blocker-induced acquisition failure cannot distinguish compression, reciprocal mixing or insufficient selectivity without additional controlled frequency/power/gain sweeps.',
            'Model-internal clipping and injected frequency error must not be exposed as measured chip telemetry.'],
        limitations=['Known-stimulus measurements are bench capabilities, not autonomous field diagnosis.',
            'Host capture throughput, firmware commands and physical analog access require end-to-end implementation verification.',
            'These signatures are bounded paired observations, not a trained fault classifier or guaranteed diagnosis under mixed faults.'])


def joined_rf_resource_screen(contract):
    """Cost the declared TX, clock and host hypotheses on the same rails."""
    base=next(c['rf'] for c in contract['behavioral_configuration_cases'] if c['id']=='wifi_he20__40000000.0')
    rows=[]
    for lo in LO_HZ:
        settings=external_settings(base,lo)
        host=clock_host_candidate(settings,contract)
        word_hz=2*host['d2h_clock_hz']
        for static,cap in ((.012,1.5e-12),(.024,3e-12),(.036,3e-12)):
            for rising in (.25,.5):
                a=replace(Assumptions(),host_clock_scale=word_hz/250e6,
                    host_data_rising_probability=rising,pll_bias_a=static+cap*3.3*lo,
                    rf_bias_a=.037,rf_output_power_w=0.)
                budget=power_budget({'engine':'rf'},a,{'directions':('rx','tx')},contract,mode=0)
                currents=dict(budget['average_current_a'])
                # Existing 7 pC per output transition hypothesis; not CORE
                # predrivers. Clock transitions every DDR word; data transition
                # probability is twice its symmetric rising probability.
                internal={'HOST_A':5*2*rising*word_hz*7e-12,
                          'HOST_B':(5*2*rising+1)*word_hz*7e-12}
                for domain,extra in internal.items():currents[domain]+=extra
                ground_drop=a.return_resistance_ohm*sum(currents.values())
                rails={domain:a.supply_v-a.feed_resistance_ohm*current-ground_drop for domain,current in currents.items()}
                remaining={domain:budget['per_connection_limits_a'][domain]-current for domain,current in currents.items()}
                rows.append(dict(lo_hz=lo,settings=settings,host=host,
                    clock_static_current_a=static,clock_equivalent_cap_f=cap,data_rising_probability=rising,
                    assigned_current_a=currents,host_internal_switching_a=internal,
                    remaining_current_allocation_a=remaining,estimated_rail_v=rails,
                    total_assigned_supply_power_w=a.supply_v*sum(currents.values()),
                    conditional_allocation_pass=min(remaining.values())>=0 and min(rails.values())>=a.minimum_supply_v and host['capacity_pass'],
                    over_budget_domains=[domain for domain,value in remaining.items() if value<0]))
    return dict(cases=rows,status='joined_assigned_costs_not_physical_fit',joint_fit_verified=False,
        assumptions=['RF 37 mA includes the 28 mA TX driver allocation; no extra RF-power/efficiency term is added to that same reservation.',
            'Host 10 pF loads and 7 pC per changed output are existing provisional hypotheses; random and alternating data activity compared.',
            'CORE remains an assigned 20 mA and clock static/current-load combinations are hypotheses. Inactive leakage and complete internal switching remain unpriced.',
            '37 mA is a demonstration reservation, not a measured bound for simultaneous RF TX/RX. This screen does not establish full-duplex capability.',
            'Simple 2 ohm supply and 0.1 ohm shared-return DC drops only; no dynamic PDN, substrate or thermal closure.'],
        unresolved=['Actual block current allocation, driver/filter tuning costs and inactive leakage',
            'Area and protected pad/clock-input bandwidth',
            'External source, board component and FPGA power',
            'Physical GPIO timing, finite paced transport and clock ownership',
            'Joint signal quality at these same rails and switching spectra'])


def rf_dc_quality_bridge(contract,resources):
    """Re-use joined DC rail in the spectral receiver, not a dynamic-PDN claim."""
    selected=[r for r in resources['cases'] if r['lo_hz']==2.437e9 and r['clock_static_current_a']==.012]
    rows=[]
    for budget in selected:
        rail=budget['estimated_rail_v']['RF']
        result=spectral_rf_mitigations(contract,seed_offsets=(0,),rf_rail_v=rail,
            clock_names=('external_clean','external_noisy'),explicit_frontend=True,
            restore_gain=True,residual_pushing_hz_per_v=65e6)
        rows.append(dict(data_rising_probability=budget['data_rising_probability'],
            rf_rail_v=rail,conditional_allocation_pass=budget['conditional_allocation_pass'],
            spectral_cases=result['cases']))
    return dict(cases=rows,status='dc_rail_join_only',
        scope=['RF gain/noise scaling in the receiver uses the exact joined-budget RF DC rail at 2.437 GHz.',
            'Same explicit board insertion loss and configured gain restoration as existing spectral comparison; assigned PGA headroom unchanged.',
            '1/10 mV ripple and 65 MHz/V residual pushing remain assigned stress inputs, not predicted switching-noise spectra from this DC ledger.',
            'Changing DC rail does not model supply-dependent ENOB, filter poles, compression, PLL tuning or transistor headroom.',
            'One phase realization; no protocol, physical current, area, dynamic coexistence or whole-chip closure claim.'])


def host_charge_pdn_bridge(contract,resources):
    """Assigned host activity charge -> clock-rail network -> RF waveform."""
    budget=next(r for r in resources['cases'] if r['lo_hz']==2.437e9 and
        r['clock_static_current_a']==.012 and r['data_rising_probability']==.25)
    word_hz=2*budget['host']['d2h_clock_hz'];rising=.25;modulation=.5
    cap_current=10*rising*word_hz*10e-12*3.3
    internal_current=10*2*rising*word_hz*7e-12
    tone_peak=modulation*(cap_current+internal_current)
    host_dc=sum(budget['assigned_current_a'][d] for d in ('HOST_A','HOST_B'))
    victim_dc=budget['assigned_current_a']['PLL']
    base=next(r for r in return_pdn_scenarios(word_hz) if r['name']=='lower_impedance_return')
    rows=[]
    for name,cap,esr,feed in [('existing_10uf',10e-6,.05,2.),('more_capacitance',20e-6,.05,2.),
                             ('lower_esr',10e-6,.02,2.),('lower_feed_resistance',10e-6,.02,.1),
                             ('lower_feed_adverse_cap',5e-6,.05,.1)]:
        network=dict(base['network'],board_c=cap,board_esr=esr,feed_r=feed)
        transfer=shared_return_transfer(1e6,return_r=.02,return_l=.5e-9,**network)
        phasor=tone_peak*transfer['differential_ohm']
        disturbance=dict(name=name,die_ripple_peak_v=abs(phasor),
            die_ripple_phase_rad=math.atan2(phasor.imag,phasor.real))
        dc_rail=3.3-(network['feed_r']+.02)*(host_dc+victim_dc)-network['package_r']*victim_dc
        peak=max(((float(f),abs(shared_return_transfer(float(f),return_r=.02,return_l=.5e-9,**network)['differential_ohm']))
                  for f in np.geomspace(1e4,1e9,251)),key=lambda x:x[1])
        result=spectral_rf_mitigations(contract,seed_offsets=(0,),rf_rail_v=budget['estimated_rail_v']['RF'],
            clock_names=('external_clean',),explicit_frontend=True,restore_gain=True,
            residual_pushing_hz_per_v=65e6,pdn_scenarios=[disturbance])
        rows.append(dict(name=name,network=network,return_r_ohm=.02,return_l_h=.5e-9,
            host_average_current_a=host_dc,clock_victim_current_a=victim_dc,
            modeled_clock_rail_dc_v=dc_rail,
            dc_board_feed_loss_w=network['feed_r']*(host_dc+victim_dc)**2,
            dc_victim_series_loss_w=network['package_r']*victim_dc**2,
            modeled_rf_rail_dc_v=budget['estimated_rail_v']['RF'],
            host_data_capacitive_average_a=cap_current,host_data_internal_average_a=internal_current,
            host_activity_current_tone_peak_a=tone_peak,**{k:v for k,v in disturbance.items() if k!='name'},
            transfer_scan_peak=dict(frequency_hz=peak[0],transimpedance_ohm=peak[1]),
            kcl_residual_a=transfer['kcl_residual_a'],spectral_cases=result['cases']))
    return dict(cases=rows,status='host_charge_coupling_candidate_not_full_chip_pdn',
        assumptions=['Random-data mean rising probability 0.25 with 50% sinusoidal activity modulation: range 0.125–0.375, inside the 0–0.5 physical bound.',
            '7 pC internal charge per transition and 10 pF external loads; their data-activity envelopes are coherent. Clock and static bias affect DC, not this 1 MHz data-activity tone.',
            'Clock victim shares board feed and the specified return with host; RF DC uses the separate joined-budget rail. No complete multi-rail package/substrate matrix is claimed.',
            'Clock-victim DC uses allocated constant currents; actual bias, tuning and phase noise versus its lower supply remain unverified.',
            'Lower feed resistance retains the existing 2 ohm victim series damping; its source output impedance and regulator stability require board implementation evidence.',
            'Board C/ESR/ESL are assigned lumped values, not selected or characterized components. Wider frequency scan is a network sensitivity screen, not a real host current spectrum.'],
        unresolved=['Actual charge waveforms and broadband/edge spectra','Shared-ground conversion into signal and reference paths',
            'Clock operation and noise at predicted local rail','Physical component/package parasitics and complete dynamic multi-rail accounting'])


def host_harmonic_current(frequency_hz,word_hz,harmonic,internal_tau_s=.5e-9):
    """Complex peak line of an assigned periodic mean host-current waveform."""
    if (type(harmonic) is not int or harmonic<1 or not all(math.isfinite(v) and v>0 for v in
            (frequency_hz,word_hz,internal_tau_s)) or not math.isclose(frequency_hz,harmonic*word_hz/2,rel_tol=1e-12)):
        raise ValueError('Positive forwarded-clock harmonic and pulse time required')
    charge=10e-12*3.3;internal_charge=7e-12
    # Capacitive charge supplied by a 10 mA rectangular charging pulse.
    width=charge/.010
    hc=np.sinc(frequency_hz*width)*np.exp(-1j*math.pi*frequency_hz*width)
    hi=1/(1+2j*math.pi*frequency_hz*internal_tau_s)
    # Forwarded-clock capacitive rising pulses repeat at half word rate.
    coefficient=charge*(word_hz/2)*hc
    if harmonic%2==0:
        # Expected random data charge repeats at word rate. Clock internal
        # charge occurs on both transitions, also at word rate.
        coefficient += word_hz*(10*.25*charge*hc+(10*.5+1)*internal_charge*hi)
    return complex(2*coefficient)


def host_harmonic_screen(coupling, word_hz=2.437e9/8, harmonics=6):
    if type(harmonics) is not int or harmonics<1:raise ValueError("Positive harmonic count required")
    word=word_hz;rows=[]
    for candidate in coupling['cases']:
        if candidate['name'] not in ('existing_10uf','lower_feed_resistance','lower_feed_adverse_cap'):continue
        for tau in (.25e-9,.5e-9,1e-9):
            tones=[]
            for harmonic in range(1,harmonics+1):
                f=harmonic*word/2
                current=host_harmonic_current(f,word,harmonic,tau)
                transfer=shared_return_transfer(f,return_r=candidate['return_r_ohm'],
                    return_l=candidate['return_l_h'],**candidate['network'])
                voltage=current*transfer['differential_ohm']
                tones.append(dict(frequency_hz=f,current_peak_a=abs(current),
                    clock_rail_voltage_peak_v=abs(voltage),voltage_phase_rad=math.atan2(voltage.imag,voltage.real)))
            rows.append(dict(network=candidate['name'],internal_charge_tau_s=tau,tones=tones,
                resolved_tone_voltage_rms_v=math.sqrt(sum(t['clock_rail_voltage_peak_v']**2/2 for t in tones)),
                omitted_harmonics_above_hz=tones[-1]['frequency_hz']))
    return dict(cases=rows,host_word_hz=word,status='periodic_mean_current_harmonics_not_full_noise_spectrum',
        scope=['Same random-data mean activity, 10 pF load, 7 pC internal charge and network hypotheses as the DC/activity screen.',
            'Capacitive current uses a 10 mA rectangular charge pulse; internal charge uses an exponential pulse with assigned 0.25/0.5/1 ns decay.',
            'Pulse origins are aligned. Coherent bank summation models a possible synchronous mean-current component, not an independently verified worst case.',
            f'{harmonics} forwarded-clock harmonics are resolved; random-data continuous spectrum, jitter and higher harmonics are omitted.',
            'Do not extrapolate the 1 MHz residual oscillator-pushing number to these frequencies. Frequency-dependent supply-to-delay/phase transfer remains unknown.',
            'No RF EVM verdict: carrier sidebands, ADC aliasing and shared-clock phase correlations require a frequency-resolved clock model.',
            'Pulse-charge accounting does not establish valid GPIO settling, receiver sampling or real device current waveforms.'])


def supply_delay_tones(tones, stages):
    """Sum correlated stage delay phasors, then integrate distinct tone power.

    Each stage is an assigned first-order supply-to-delay transfer. This is
    propagation through buffers/dividers, not an oscillator-pushing model.
    Sensitivity is ps/mV at DC; pole_hz and latency_s preserve frequency/phase.
    """
    result=[]
    if not stages: raise ValueError('At least one explicit stage required')
    for stage in stages:
        if not all(math.isfinite(stage[k]) for k in ('ps_per_mv','pole_hz','latency_s')) or stage['pole_hz']<=0 or stage['latency_s']<0:
            raise ValueError('Finite sensitivity, positive pole and nonnegative latency required')
    frequencies=set()
    for tone in tones:
        f=tone['frequency_hz'];v=tone['clock_rail_voltage_peak_v'];phase=tone['voltage_phase_rad']
        if not all(math.isfinite(x) for x in (f,v,phase)) or f<=0 or v<0 or f in frequencies:
            raise ValueError('Unique positive tone frequencies and finite nonnegative amplitudes required')
        frequencies.add(f)
        h=sum(stage['ps_per_mv']*1e-9/(1+1j*f/stage['pole_hz'])*
              np.exp(-2j*math.pi*f*stage['latency_s']) for stage in stages)
        dt=v*np.exp(1j*phase)*h
        result.append(dict(frequency_hz=f,delay_peak_s=abs(dt),delay_phase_rad=float(np.angle(dt))))
    return dict(tones=result,rms_delay_s=math.sqrt(sum(x['delay_peak_s']**2/2 for x in result)),
                conservative_peak_delay_s=sum(x['delay_peak_s'] for x in result))


def shared_timing_requirements(harmonics):
    """One rail spectrum drives RF and wired inverse timing requirements.

    No protocol pass verdict: the physical delay sensitivities are unknown.
    RF metric is exact untracked unit-carrier phase error, before channel
    filtering/recovery; it is deliberately not called received packet EVM.
    """
    rows=[];carrier=2.437e9
    for case in harmonics['cases']:
        for pole in (10e6,100e6,1e9):
            # Unit aggregate DC sensitivity split across three coherent stages.
            stages=[dict(name=n,ps_per_mv=w,pole_hz=pole,latency_s=0.) for n,w in
                    [('input_buffer',.2),('phase_generation',.3),('distribution',.5)]]
            unit=supply_delay_tones(case['tones'],stages)
            rms_ps=unit['rms_delay_s']*1e12
            f0=min(t['frequency_hz'] for t in unit['tones'])
            t=np.arange(4096)/(4096*f0)
            dt=sum(x['delay_peak_s']*np.cos(2*math.pi*x['frequency_hz']*t+x['delay_phase_rad']) for x in unit['tones'])
            studies=[]
            for sensitivity in (.01,.1,1.):
                phase=2*math.pi*carrier*dt*sensitivity
                studies.append(dict(aggregate_dc_ps_per_mv=sensitivity,
                    rms_delay_ps=rms_ps*sensitivity,
                    peak_delay_bound_ps=unit['conservative_peak_delay_s']*1e12*sensitivity,
                    wired_2p5g_rms_ui=rms_ps*sensitivity/400.,
                    rf_untracked_carrier_error_rms=float(np.sqrt(np.mean(abs(np.exp(1j*phase)-1)**2))),
                    sample_9mhz_small_error_rms=2*math.pi*9e6*unit['rms_delay_s']*sensitivity))
            rows.append(dict(network=case['network'],internal_charge_tau_s=case['internal_charge_tau_s'],
                stage_pole_hz=pole,unit_aggregate_dc_ps_per_mv=1.,coherent_stages=stages,
                unit_response=unit,assigned_sensitivity_studies=studies,
                aggregate_dc_sensitivity_ceiling_ps_per_mv=dict(
                    wired_2ps_rms_allocation=2./rms_ps,
                    rf_5percent_small_phase_allocation=.05/(2*math.pi*carrier*unit['rms_delay_s']))))
    return dict(status='inverse_requirements_not_qualified_stage_performance',cases=rows,
        environment='Same host harmonic rail spectra feed RF LO, sample-clock and wired timing calculations.',
        assumptions=['Three coherent same-rail stages; weighted first-order sensitivities are hypotheses, not fitted GF180 data.',
            '2 ps wired allocation and 5% RF small-phase allocation are diagnostic budgets, not protocol acceptance masks.',
            'RF carrier metric precedes filtering and tracking; far-out sidebands do not equal in-band received EVM.',
            '9 MHz sample-clock metric is the small-error bound for a sinusoidal baseband input, not converter ENOB.',
            'Independent incoming wired source assumed; no cancellation credited between source and receiver.',
            'Source noise, oscillator pushing/PLL response, broadband supply noise and analog gain/reference coupling must still be joined.',
            'Peak sum is conservative; exact waveform uses one host period and all six resolved harmonics.',
            'Shared rail topology is still an assigned network; provider-compatible bond and board map remains open.'],
        complete=False)


def rf_transition_requirements():
    from resource_configuration import rf_transition_budget
    before=dict(sample_hz=2.437e9/64,tx_cutoff_hz=10e6,rx_cutoff_hz=9e6,
                sample_clock_source='external_lo',lo_hz=2.437e9,lo_divider=64)
    after=dict(before,sample_hz=2.480e9/64,lo_hz=2.480e9)
    rows=[]
    common=dict(epoch=7,host_word_hz=312.5e6,command_words=8,cdc_cycles=2,
                control_hz=40e6,boundary_wait_s=64/(2.437e9/8))
    # Budgets are diagnostic response windows, not blanket protocol constants.
    for deadline in (10e-6,150e-6,192e-6):
        for settle in (2e-6,12e-6):
            for prearmed in (False,True):
                rows.append(rf_transition_budget(before=before,after=before,operation='turnaround',
                    analog_settle_s=settle,source_lock_s=0.,host_training_words=0,fpga_recovery_s=0.,
                    deadline_s=deadline,prearmed=prearmed,**common))
        for lock in (20e-6,200e-6):
            for fixed in (None,156.25e6):
                rows.append(rf_transition_budget(before=before,after=after,operation='retune',
                    analog_settle_s=2e-6,source_lock_s=lock,host_training_words=128,fpga_recovery_s=2e-6,
                    deadline_s=deadline,fixed_host_clock_hz=fixed,**common))
    rows.append(rf_transition_budget(before=before,after=before,operation='fault_recovery',
        analog_settle_s=2e-6,source_lock_s=20e-6,host_training_words=128,fpga_recovery_s=2e-6,
        deadline_s=150e-6,**common))
    return dict(cases=rows,complete=False,physical_timing_qualified=False,
        assumptions=['Command/CDC, analog settling, source lock and FPGA recovery are explicit assigned bounds.',
            'Prearmed path must receive a valid schedule early enough; no free instantaneous host decision.',
            'Fixed-host alternative assumes a separately supplied/routed clock whose area/power/input cost is unqualified.',
            'Converter remains LO-derived in both alternatives; fixed host clock alone does not prevent sample-rate changes.',
            'Retune/fault recovery discards old epoch; same-channel turnaround must not reset qualified timing.',
            'Hardware gate integrity, actual analog transients, live-stream epoch enforcement and real packet deadlines remain open.'])


def host_driven_wired_receiver(coupling):
    # Same assigned network/pulse model; wired host has its own explicit rate.
    harmonics=host_harmonic_screen(coupling,word_hz=312.5e6)
    rail=max(harmonics['cases'],key=lambda x:x['resolved_tone_voltage_rms_v'])
    scenarios=[dict(name='zero_supply_timing_control',delay_tones=[])]
    for pole in (100e6,1e9):
        for sensitivity in (.01,.1,1.):
            response=supply_delay_tones(rail['tones'],[
                dict(ps_per_mv=sensitivity*w,pole_hz=pole,latency_s=0.) for w in (.2,.3,.5)])
            scenarios.append(dict(name=f'pole_{pole:g}_sensitivity_{sensitivity:g}',delay_tones=response['tones']))
    result=causal_receiver_envelope(timing_scenarios=scenarios)
    return dict(host_word_hz=312.5e6,rail_case=rail,receiver=result,complete=False,
        scope=['Same network and pulse-charge hypotheses as RF, evaluated at the explicit wired host word rate.',
            'Largest resolved rail RMS among sampled networks selected for this screen; not a proven physical worst case.',
            'Host rail phasors propagate through coherent stage delay responses into all four receiver voltage observations.',
            'Independent incoming source; no transmitter jitter or shared-clock cancellation included.',
            'No standards BER claim; persistent host service, actual pad/rail topology and other correlated analog errors remain open.'])


def host_driven_rf_receiver(contract,coupling):
    harmonics=host_harmonic_screen(coupling)
    rail=max(harmonics['cases'],key=lambda x:x['resolved_tone_voltage_rms_v'])
    carrier=2.437e9
    base=next(x['rf'] for x in contract['behavioral_configuration_cases'] if x['id']=='wifi_he20__40000000.0')
    settings=external_settings(base,carrier)
    source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-115.,floor_dbc_hz=-145.,
                              offset_band_hz=(1e3,8e6),bins=16,seed=831)
    rows=[]
    for sensitivity in (0.,.1,.3):
        response=supply_delay_tones(rail['tones'],[dict(ps_per_mv=sensitivity,pole_hz=1e9,latency_s=0.)])
        phase=source.plus(PhaseNoise(tuple((x['frequency_hz'],-2*math.pi*carrier*x['delay_peak_s'],x['delay_phase_rad']) for x in response['tones'])))
        for attenuation in (0.,20.):
            loss=2. if attenuation else 0.
            for steps in (64,128):
                a=replace(Assumptions(),converter_enob=8.,frontend_evm_rms=.04,
                          relative_lo_phase_rms_rad=0.,sample_jitter_s=.3e-12)
                q=waveform_screen(fixture('wifi_he20',seed=81),a,{'estimated_rail_v':{'RF':3.21}},
                    settings=settings,recover_carrier=True,fpga_resampling=True,
                    blocker=dict(offset_hz=12e6,relative_power_db=20.-attenuation+loss),
                    mixer_phase_noise=phase,sample_phase_noise=phase,mixer_substeps=steps,
                    frontend_loss_db=loss,frontend_saturation_v=2.,pga_peak_limit_v=.8)
                rows.append(dict(aggregate_dc_ps_per_mv=sensitivity,stage_pole_hz=1e9,
                    board_blocker_attenuation_db=attenuation,board_wanted_loss_db=loss,
                    mixer_substeps=steps,quality=summarize_quality(q),spectral_clock=q['spectral_clock']))
    return dict(cases=rows,rail_case=rail,host_word_hz=harmonics['host_word_hz'],complete=False,
        scope=['Same assigned host/package spectra as the timing screen, now passed through RX mixing, analog filtering, converter and acquisition.',
            'D2H clock and conversion derive coherently from the same LO; H2D independent-clock current injection is not included.',
            'Shared phase perturbs mixer and implicit ADC crossings; source waveform has independent ideal timing.',
            'Assigned clean source spectrum plus host delay tones, fixed 3.21 V RF rail, 8 ENOB and frontend noise; no physical qualification.',
            '12 MHz blocker and external 20 dB preselection/2 dB insertion loss are hypotheses, not standard masks.',
            '64/128 substep comparison checks numerical sensitivity; higher nonlinear sidebands and device bandwidth remain unqualified.',
            'Diagnostic HE20 BPSK and synthetic acquisition prefix; real protocol packets, emissions and turnaround remain open.'])


def h2d_current_ports(frequency_hz,word_hz,harmonic,*,input_cap_f=5e-12,
                      internal_charge_c=.3e-12,alternating=False,origin_s=0.):
    """H2D current at distinct chip supply and capacitive-return ports.

    FPGA charging power is external. Capacitive return is signed displacement
    current, not a second chip supply load. Random data has zero periodic mean
    displacement; its omitted continuous spectrum is not assumed physically zero.
    """
    if type(harmonic) is not int or harmonic<1 or not math.isclose(frequency_hz,harmonic*word_hz/2,rel_tol=1e-12):
        raise ValueError('H2D forwarded-clock harmonic required')
    if not all(math.isfinite(v) for v in (frequency_hz,word_hz,input_cap_f,internal_charge_c,origin_s)) or min(frequency_hz,word_hz,input_cap_f)<=0 or internal_charge_c<0:
        raise ValueError('Physical finite port parameters required')
    q=input_cap_f*3.3;width=q/.01
    pulse=np.sinc(frequency_hz*width)*np.exp(-1j*math.pi*frequency_hz*width)
    phase=np.exp(-2j*math.pi*frequency_hz*origin_s)
    active_lines=11 if alternating else 1
    external_return=2*active_lines*q*(word_hz/2)*(1-(-1)**harmonic)*pulse*phase
    internal=0j
    if harmonic%2==0:
        transitions=11 if alternating else 6
        internal=2*transitions*internal_charge_c*word_hz/(1+2j*math.pi*frequency_hz*.5e-9)*phase
    return dict(chip_internal_peak_a=complex(internal),external_cap_return_peak_a=complex(external_return))


def bidirectional_host_spectrum(coupling,*,d2h_word_hz=2.437e9/8,internal_charge_c=.3e-12,
                                alternating=False,origin_s=0.,return_fraction=1.,d2h_harmonics=6,
                                d2h_internal_tau_s=None):
    if not 0<=return_fraction<=1:raise ValueError('Bounded external-return participation required')
    d2h=host_harmonic_screen(coupling,word_hz=d2h_word_hz,harmonics=d2h_harmonics)
    candidates=d2h['cases'] if d2h_internal_tau_s is None else [x for x in d2h['cases'] if x['internal_charge_tau_s']==d2h_internal_tau_s]
    if not candidates:raise ValueError('Explicit D2H pulse shape is not one of the modeled hypotheses')
    rail=max(candidates,key=lambda x:x['resolved_tone_voltage_rms_v'])
    network=next(x for x in coupling['cases'] if x['name']==rail['network'])
    common=dict(return_r=network['return_r_ohm'],return_l=network['return_l_h'],**network['network'])
    combined={x['frequency_hz']:x['clock_rail_voltage_peak_v']*np.exp(1j*x['voltage_phase_rad']) for x in rail['tones']}
    rows=[]
    for n in range(1,7):
        f=n*312.5e6/2
        currents=h2d_current_ports(f,312.5e6,n,internal_charge_c=internal_charge_c,
                                   alternating=alternating,origin_s=origin_s)
        internal=shared_return_transfer(f,injection_weights=(0.,-1.,1.),**common)
        external=shared_return_transfer(f,injection_weights=(0.,0.,return_fraction),**common)
        vi=currents['chip_internal_peak_a']*internal['differential_ohm']
        ve=currents['external_cap_return_peak_a']*external['differential_ohm']
        combined[f]=combined.get(f,0j)+vi+ve
        rows.append(dict(frequency_hz=f,chip_internal_current_peak_a=abs(currents['chip_internal_peak_a']),
            external_cap_return_current_peak_a=abs(currents['external_cap_return_peak_a']),
            internal_rail_voltage_peak_v=abs(vi),external_return_rail_voltage_peak_v=abs(ve),
            combined_h2d_rail_voltage_peak_v=abs(vi+ve),
            kcl_residual_a=max(internal['kcl_residual_a'],external['kcl_residual_a']),
            power_residual_w=max(abs(internal['power_residual_w']),abs(external['power_residual_w']))))
    tones=[dict(frequency_hz=f,clock_rail_voltage_peak_v=float(abs(v)),voltage_phase_rad=float(np.angle(v))) for f,v in sorted(combined.items())]
    return dict(d2h_word_hz=d2h_word_hz,h2d_word_hz=312.5e6,network=rail['network'],
        internal_charge_c=internal_charge_c,alternating=alternating,h2d_origin_s=origin_s,
        d2h_internal_tau_s=rail['internal_charge_tau_s'],
        chip_h2d_internal_mean_a=(11 if alternating else 6)*internal_charge_c*312.5e6,
        fpga_external_capacitive_mean_a=(5.5 if alternating else 3.)*5e-12*3.3*312.5e6,
        external_capacitive_signed_return_mean_a=0.,
        external_return_fraction=return_fraction,h2d_ports=rows,tones=tones,
        resolved_rail_rms_v=math.sqrt(sum(x['clock_rail_voltage_peak_v']**2/2 for x in tones)),
        scope='Assigned common victim PDN: internal load at die supply, external capacitive current at die return; actual shared topology unqualified')


def bidirectional_host_receiver_screen(contract,coupling):
    carrier=2.437e9
    base=next(x['rf'] for x in contract['behavioral_configuration_cases'] if x['id']=='wifi_he20__40000000.0')
    settings=external_settings(base,carrier);rows=[];wired_scenarios=[];wired_environments=[]
    for charge,alternating in ((.3e-12,False),(.3e-12,True),(7e-12,True)):
        for origin in (0.,1/(4*156.25e6)):
            environment=bidirectional_host_spectrum(coupling,internal_charge_c=charge,alternating=alternating,origin_s=origin)
            delay=supply_delay_tones(environment['tones'],[dict(ps_per_mv=.1,pole_hz=1e9,latency_s=0.)])
            phase=PhaseNoise(tuple((x['frequency_hz'],-2*math.pi*carrier*x['delay_peak_s'],x['delay_phase_rad']) for x in delay['tones']))
            source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-115.,floor_dbc_hz=-145.,offset_band_hz=(1e3,8e6),bins=16,seed=831)
            phase=phase.plus(source)
            q=waveform_screen(fixture('wifi_he20',seed=81),replace(Assumptions(),converter_enob=8.,frontend_evm_rms=.04,
                relative_lo_phase_rms_rad=0.,sample_jitter_s=.3e-12),{'estimated_rail_v':{'RF':3.21}},
                settings=settings,recover_carrier=True,fpga_resampling=True,
                blocker=dict(offset_hz=12e6,relative_power_db=2.),frontend_loss_db=2.,
                frontend_saturation_v=2.,pga_peak_limit_v=.8,mixer_phase_noise=phase,sample_phase_noise=phase,mixer_substeps=128)
            rows.append(dict(environment=environment,quality=summarize_quality(q),spectral_clock=q['spectral_clock']))
            wire_environment=bidirectional_host_spectrum(coupling,d2h_word_hz=312.5e6,
                internal_charge_c=charge,alternating=alternating,origin_s=origin)
            wire_delay=supply_delay_tones(wire_environment['tones'],[dict(ps_per_mv=.1,pole_hz=1e9,latency_s=0.)])
            name=f'charge_{charge:g}_alternate_{alternating}_origin_{origin:g}'
            wired_scenarios.append(dict(name=name,delay_tones=wire_delay['tones']))
            wired_environments.append(dict(name=name,environment=wire_environment))
    return dict(cases=rows,wired_environments=wired_environments,
        wired_receiver=causal_receiver_envelope(timing_scenarios=wired_scenarios),complete=False,assumptions=[
        'H2D input capacitance 5 pF and internal transition charge 0.3/7 pC are assigned study points, not proven device bounds.',
        'Independent H2D forwarded clock 156.25 MHz; D2H and conversion remain LO-derived. Relative origins are explicit.',
        'Alternating H2D data aligns ten data lines with its clock; random-data continuous return spectrum is omitted.',
        'External capacitive current injects only return current; FPGA output CVf power is not charged to chip supply.',
        'Chip input/internal charge loads the victim die rail as a shared-rail stress; real local isolation and board topology remain open.',
        'Same 0.1 ps/mV aggregate delay, 1 GHz pole and external filter hypotheses as preceding RF study.',
        'DC current fields distinguish chip and FPGA demand; they must be reconciled with existing host allocations, not blindly added twice.',
        'RF rail remains the assigned 3.21 V fixture: complete common-rail DC and supply-dependent bias are not established.',
        'High-ripple stress may invalidate linear delay/PDN hypotheses; no physical fail/pass is inferred.',
        'Analog reference/gain modulation, supply-dependent bias/startup and real protocol packets remain unjoined.'])


def common_feed_dc_ledger(contract,*,lo_hz=2.437e9,h2d_internal_charge_c=.3e-12,
                          h2d_alternating=False,d2h_rising_probability=.25,
                          feed_r=.1,branch_r=2.,return_r=.02,source_v=3.3,d2h_word_hz=None,
                          payload_engine="rf",payload_current_a=.037):
    """One common external feed, one assigned local analog/control branch.

    Logical domains are loads, not independently powered external rails.
    HOST sits at the feed node; CORE/PLL/RF/H2D-internal share the victim branch.
    This topology is a hypothesis awaiting compatible ring/board mapping.
    """
    if payload_engine not in ("rf","wire") or not math.isfinite(payload_current_a) or payload_current_a<0:
        raise ValueError("Explicit RF or wired nonnegative payload current required")
    values=(lo_hz,h2d_internal_charge_c,d2h_rising_probability,feed_r,branch_r,return_r,source_v)
    if not all(math.isfinite(x) for x in values) or min(lo_hz,source_v)<=0 or min(h2d_internal_charge_c,feed_r,branch_r,return_r)<0 or not 0<=d2h_rising_probability<=.5:
        raise ValueError('Finite passive common-feed ledger required')
    word=lo_hz/8 if d2h_word_hz is None else d2h_word_hz
    if not math.isfinite(word) or word<=0:raise ValueError('Positive finite D2H rate required')
    rise=d2h_rising_probability
    d2h_cap=(10*rise+.5)*word*10e-12*source_v
    d2h_internal=(20*rise+1)*word*7e-12
    h2d_internal=(11 if h2d_alternating else 6)*312.5e6*h2d_internal_charge_c
    loads=dict(core_excluding_host_io=.020,clock=.012+1.5e-12*source_v*lo_hz,
        host_static=.004,
        d2h_capacitive=d2h_cap,d2h_internal=d2h_internal,h2d_internal=h2d_internal)
    loads['rf_driver_and_conversion_reservation' if payload_engine=='rf' else 'wired_frontend_reservation']=payload_current_a
    host=loads['host_static']+d2h_cap+d2h_internal
    local=sum(loads.values())-host;total=host+local
    board=source_v-feed_r*total
    ground=return_r*total
    victim=board-branch_r*local-ground
    host_rail=board-ground
    source_power=source_v*total
    losses=dict(common_feed=feed_r*total**2,local_branch=branch_r*local**2,shared_return=return_r*total**2)
    # Delivered electrical power, not an on-die heat estimate: D2H load charging
    # dissipates across chip outputs and external loads.
    delivered=host*host_rail+local*victim
    return dict(source_v=source_v,d2h_word_hz=word,loads_a=loads,host_node_current_a=host,local_branch_current_a=local,
        total_chip_supply_current_a=total,board_supply_v=board,die_return_v=ground,
        rf_clock_core_rail_v=victim,local_payload_clock_core_rail_v=victim,
        payload_engine=payload_engine,payload_current_a=payload_current_a,host_rail_v=host_rail,
        source_power_w=source_power,resistive_losses_w=losses,delivered_electrical_power_w=delivered,
        power_balance_residual_w=source_power-delivered-sum(losses.values()),
        h2d_external_fpga_capacitive_current_a=(5.5 if h2d_alternating else 3.)*312.5e6*5e-12*source_v,
        min_fixture_rail_v=2.5,inside_assigned_voltage_range=min(victim,host_rail)>=2.5,
        physical_pin_current_qualification=False,
        assumptions=['Constant-current first pass; supply-dependent switching/bias must be solved self-consistently later.',
            'CORE 20 mA excludes explicitly itemized host input/output switching by allocation definition, not measurement.',
            'Payload current is one explicit reservation, not demonstrated consumption; RF default includes the TX driver. Wired use here requires locally supplied termination current within that reservation; external termination return current needs a separate port.',
            'Inactive leakage, SPI/reset/control pad switching and complete reference/bias implementation remain unpriced.',
            'H2D FPGA capacitive power stays external; signed capacitive return averages zero.',
            'External topology and bond-current distribution remain unverified; no independent logical-rail feeds implied.'])


def operating_environment(contract, candidate, *, carrier_hz, d2h_word_hz,
                          payload_engine, payload_current_a, h2d_internal_charge_c,
                          d2h_harmonics=6, clock_sensitivity_ps_per_mv=.1,
                          reference_fraction_per_v=0., reference_pole_hz=1e9,
                          d2h_internal_tau_s=.5e-9,external_input=None):
    """One explicit DC/AC/timing environment, consumed by either payload path.

    No best-network selection: the caller names the actual candidate network.
    Device transfer functions and source spectra remain assigned hypotheses.
    """
    for value in (carrier_hz,d2h_word_hz,reference_pole_hz):
        if not math.isfinite(value) or value<=0:raise ValueError('Positive finite operating rate required')
    if not math.isfinite(reference_fraction_per_v) or reference_fraction_per_v<0:
        raise ValueError('Nonnegative reference feedthrough required')
    environment=bidirectional_host_spectrum(dict(cases=[candidate]),
        d2h_word_hz=d2h_word_hz,internal_charge_c=h2d_internal_charge_c,
        alternating=True,d2h_harmonics=d2h_harmonics,d2h_internal_tau_s=d2h_internal_tau_s)
    ledger=common_feed_dc_ledger(contract,lo_hz=carrier_hz,
        h2d_internal_charge_c=h2d_internal_charge_c,h2d_alternating=True,
        feed_r=candidate['network']['feed_r'],branch_r=candidate['network']['package_r'],
        return_r=candidate['return_r_ohm'],d2h_word_hz=d2h_word_hz,
        payload_engine=payload_engine,payload_current_a=payload_current_a)
    delay=supply_delay_tones(environment['tones'],[
        dict(ps_per_mv=clock_sensitivity_ps_per_mv,pole_hz=1e9,latency_s=0.)])
    source=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-115.,floor_dbc_hz=-145.,
        offset_band_hz=(1e3,8e6),bins=16,seed=831)
    phase=source.plus(PhaseNoise(tuple((x['frequency_hz'],
        -2*math.pi*carrier_hz*x['delay_peak_s'],x['delay_phase_rad']) for x in delay['tones'])))
    input_report=None
    if external_input is not None:
        input_phase,input_report=loaded_clock_input_phase(carrier_hz,**external_input)
        phase=phase.plus(input_phase)
    # Sampling time displacement is negative phase / angular carrier frequency.
    crossing=[dict(frequency_hz=f,delay_peak_s=abs(a)/(2*math.pi*carrier_hz),
        delay_phase_rad=p+(math.pi if a>0 else 0.)) for f,a,p in phase.tones]
    reference=[]
    for tone in environment['tones']:
        h=reference_fraction_per_v/(1+1j*tone['frequency_hz']/reference_pole_hz)
        v=tone['clock_rail_voltage_peak_v']*np.exp(1j*tone['voltage_phase_rad'])*h
        reference.append((tone['frequency_hz'],float(abs(v)),float(np.angle(v))))
    return dict(payload_engine=payload_engine,carrier_hz=carrier_hz,
        network=candidate,ledger=ledger,host_spectrum=environment,external_clock_input=input_report,
        supply_delay=delay,delivered_phase_tones=phase.tones,
        crossing_delay_tones=crossing,reference_fraction_tones=reference,
        source_spectrum=dict(colored_at_100khz_dbc_hz=-115.,floor_dbc_hz=-145.,
            offset_band_hz=[1e3,8e6],location=('assigned external source before loaded receiver' if external_input is not None else 'assigned delivered source before supply-delay contribution')),
        clock_sensitivity_ps_per_mv=clock_sensitivity_ps_per_mv,
        reference_fraction_per_v=reference_fraction_per_v,reference_pole_hz=reference_pole_hz,
        complete=False,
        limitations=['Shared network and immutable spectral realization, not a measured physical corner.',
            'Source noise is a delivered-clock requirement; autonomous synthesis and external input/additive stages have not demonstrated it.',
            'D2H random mean and H2D alternating stress; continuous random spectrum and payload switching currents omitted.',
            'Current/headroom/NF versus rail, independent local jitter, startup and nonlinear supply response remain unqualified.',
            'Legacy rf_clock_core_rail_v aliases the local rail in wired mode; it does not activate RF.'])


def environment_reference_scale(environment, times):
    return 1+sum(a*np.cos(2*math.pi*f*times+p)
        for f,a,p in environment['reference_fraction_tones'])


def common_feed_rf_screen(contract,coupling,*,clock_sensitivity_ps_per_mv=.1,reference_fraction_per_v=0.,reference_pole_hz=1e9,d2h_word_hz=2.437e9/8,d2h_harmonics=6,frontend_evm_rms=.04):
    """Join both host directions, common-feed DC and RX observation."""
    if not all(math.isfinite(v) for v in (clock_sensitivity_ps_per_mv,reference_fraction_per_v,reference_pole_hz)) or min(clock_sensitivity_ps_per_mv,reference_fraction_per_v)<0 or reference_pole_hz<=0:
        raise ValueError('Finite nonnegative coupling and positive reference pole required')
    carrier=2.437e9
    base=next(x['rf'] for x in contract['behavioral_configuration_cases'] if x['id']=='wifi_he20__40000000.0')
    settings=external_settings(base,carrier);rows=[]
    # Use the same network selected by the bidirectional harmonic comparison.
    for charge in (.3e-12,7e-12):
        for feed in (.1,2.):
            # Pin the candidate network; selection does not cherry-pick another
            # network after changing the common source impedance.
            original=next(x for x in coupling['cases'] if x['name']=='lower_feed_resistance')
            candidate=dict(original,network=dict(original['network'],feed_r=feed))
            joined=operating_environment(contract,candidate,carrier_hz=carrier,
                d2h_word_hz=d2h_word_hz,payload_engine='rf',payload_current_a=.037,
                h2d_internal_charge_c=charge,d2h_harmonics=d2h_harmonics,
                clock_sensitivity_ps_per_mv=clock_sensitivity_ps_per_mv,
                reference_fraction_per_v=reference_fraction_per_v,reference_pole_hz=reference_pole_hz,
                d2h_internal_tau_s=None)
            environment=joined['host_spectrum'];ledger=joined['ledger']
            phase=PhaseNoise(tuple(joined['delivered_phase_tones']))
            rail=ledger['local_payload_clock_core_rail_v']
            def reference_scale(times):return environment_reference_scale(joined,times)

            q=waveform_screen(fixture('wifi_he20',seed=81),replace(Assumptions(),converter_enob=8.,frontend_evm_rms=frontend_evm_rms,
                relative_lo_phase_rms_rad=0.,sample_jitter_s=.3e-12),{'estimated_rail_v':{'RF':rail}},
                settings=settings,recover_carrier=True,fpga_resampling=True,
                blocker=dict(offset_hz=12e6,relative_power_db=2.),frontend_loss_db=2.,
                frontend_saturation_v=2.,pga_peak_limit_v=.8*rail/3.3,
                mixer_phase_noise=phase,sample_phase_noise=phase,mixer_substeps=128,adc_reference_scale=reference_scale)
            rows.append(dict(feed_r_ohm=feed,h2d_internal_charge_c=charge,ledger=ledger,
                environment=environment,quality=summarize_quality(q),pga_headroom=q['pga_headroom'],
                clock_sensitivity_ps_per_mv=clock_sensitivity_ps_per_mv,reference_fraction_per_v=reference_fraction_per_v,
                reference_pole_hz=reference_pole_hz,reference_modulation=q['reference_modulation']))
    return dict(cases=rows,complete=False,status='common_feed_dc_and_timing_join_not_physical_power_closure',
        limitations=['RF gain/noise scaling and assigned PGA headroom now use the calculated shared-feed rail.',
            'PLL startup/noise/tuning, filter poles, ENOB and reference accuracy versus DC supply remain unmodeled.',
            'Optional ADC-reference modulation is assigned linear feedthrough; PGA gain modulation and physical reference output impedance remain open.',
            'Constant-current loads and linear AC network do not establish large-ripple physical behavior.',
            'Selected local-branch topology must fit the fixed COB/ring power connectivity; not a claim of compatible realization.'])


def shared_board_candidate(board_cap_f=1e-6):
    """Assigned common network; Run 1 only supplies the 1 uF footprint label."""
    return dict(name='lower_feed_resistance',return_r_ohm=.02,return_l_h=.5e-9,
        network=dict(feed_r=.1,feed_l=2e-9,package_r=2.,package_l=2e-9,
            die_c=100e-12,board_c=board_cap_f,board_esr=.02,board_esl=1e-9))


def local_load_state_space(candidate):
    """Same passive PDN as shared_return_transfer, driven by local load slope.

    States: feed current, die-cap current, board-cap voltage, die-cap voltage,
    local load current. All are perturbations about an already settled load.
    Input is dIload/dt; output is die supply minus die return perturbation.
    No node is reset when the load changes direction.
    """
    from scipy.signal import StateSpace
    n=candidate['network']
    rf,lf=n['feed_r'],n['feed_l']
    rp=n['package_r']+candidate['return_r_ohm']
    lp=n['package_l']+candidate['return_l_h']
    rb,lb,cb=n['board_esr'],n['board_esl'],n['board_c']
    rd,ld,cd=n.get('die_esr',0.),n.get('die_esl',0.),n['die_c']
    if not all(math.isfinite(v) and v>=0 for v in (rf,lf,rp,lp,rb,lb,rd,ld)) or not all(math.isfinite(v) and v>0 for v in (cb,cd)):
        raise ValueError('Finite passive network and positive capacitors required')
    inductance=np.array([[lf+lb,-lb],[-lb,lp+ld+lb]])
    if np.linalg.det(inductance)<=0:
        raise ValueError('Nonsingular positive inductance network required')
    def derivative(x,u):
        i,ic,vb,vc,load=x
        di,dic=np.linalg.solve(inductance,[-(rf+rb)*i+rb*(load+ic)-vb+lb*u,
            vb-vc+rb*i-(rb+rp)*load-(rb+rp+rd)*ic-(lb+lp)*u])
        return np.array([di,dic,(i-load-ic)/cb,ic/cd,u])
    zero=np.zeros(5)
    a=np.column_stack([derivative(x,0.) for x in np.eye(5)])
    b=derivative(zero,1.)[:,None]
    c=np.array([[0.,rd,0.,1.,0.]])+ld*a[1:2,:]
    d=ld*b[1:2,:]
    return StateSpace(a,b,c,d)


def analog_wake_envelope():
    """Fast state-continuous incremental TX-bias disturbance, not packet proof."""
    from scipy.signal import lsim
    candidate=shared_board_candidate()
    candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
    system=local_load_state_space(candidate)
    # A 2 ns output grid; ZOH load slope integrates exact linear ramps between
    # grid boundaries. Internal RLC state propagation uses matrix exponentials.
    dt=2e-9;t=np.arange(10001)*dt
    rows=[]
    for step in (0.,.007,.028):
        for ramp in (20e-9,100e-9,1e-6):
            slope=np.zeros(len(t));start=1000;stop=3000;count=round(ramp/dt)
            slope[start:start+count]=step/ramp
            slope[stop:stop+count]=-step/ramp
            _,voltage,state=lsim(system,U=slope,T=t,interp=False)
            # Illustrative existing 0.1 ps/mV sensitivity and 1 GHz pole.
            from scipy.signal import StateSpace
            pole=2*math.pi*1e9
            _,filtered,_=lsim(StateSpace([[-pole]],[[pole]],[[1.]],[[0.]]),U=voltage,T=t)
            residual=abs(voltage[stop+count:])
            bad=np.flatnonzero(residual>1e-3)
            settle=None if len(bad) and bad[-1]==len(residual)-1 else (0. if not len(bad) else float((bad[-1]+1)*dt))
            rows.append(dict(load_step_a=step,ramp_s=ramp,peak_droop_v=float(-min(voltage)),
                peak_overshoot_v=float(max(voltage)),
                plateau_droop_v=float(-voltage[stop-1]),
                dc_expected_drop_v=step*(candidate['network']['feed_r']+candidate['network']['package_r']+candidate['return_r_ohm']),
                peak_assigned_clock_shift_s=float(max(abs(filtered))*1e-10),
                residual_2us_after_mute_v=float(voltage[stop+count+1000]),
                mute_recovery_to_1mv_s=settle,
                final_load_a=float(state[-1,4]),final_rail_perturbation_v=float(voltage[-1])))
    return dict(candidate=candidate,cases=rows,load_on_s=2e-6,load_off_s=6e-6,
        observation_end_s=float(t[-1]),sample_interval_s=dt,
        complete=False,scope='Incremental local-current wake/mute on the existing passive supply/return network. Zero step represents ideal constant-current warm bias only; actual unmute load changes remain unknown. 7 mA is a sensitivity point, not a predicted warm-mode change. 28 mA is the full assigned driver reservation. Existing host ripple, source noise and initial DC rail must be superposed before any rail or packet acceptance. No converter settling, RF switching, substrate injection, supply-dependent current, TX spectral mask or protocol deadline is qualified. The 1 mV recovery marker is diagnostic, not a chip specification.')


def local_decoupling_envelope(contract):
    """Area-aware shared-rail hypotheses; no extracted capacitor is implied."""
    rows=[]
    for cap in (100e-12,500e-12,1e-9):
        for esr,esl in ((0.,0.),(.1,50e-12),(.5,200e-12),(1.,1e-9)):
            for mode,carrier,rate,current in (
                    ('rf',2.437e9,2.437e9/16,.037),('wire',2.5e9,312.5e6,.096)):
                candidate=shared_board_candidate()
                candidate['network'].update(die_c=cap,die_esr=esr,die_esl=esl)
                e=operating_environment(contract,candidate,carrier_hz=carrier,
                    d2h_word_hz=rate,payload_engine=mode,payload_current_a=current,
                    h2d_internal_charge_c=7e-12)
                dc=e['ledger']['local_payload_clock_core_rail_v']
                peak=sum(x['clock_rail_voltage_peak_v'] for x in e['host_spectrum']['tones'])
                jitter=math.sqrt(sum(x['delay_peak_s']**2/2 for x in e['supply_delay']['tones']))
                rows.append(dict(mode=mode,cap_f=cap,esr_ohm=esr,esl_h=esl,
                    ideal_plate_mm2_at_min_density=[cap/d/1e6 for d in (.9e-15,1.27e-15,1.8e-15)],
                    rail_interval_v=[dc-peak,dc+peak],rail_rms_v=e['host_spectrum']['resolved_rail_rms_v'],
                    supply_delay_rms_s=jitter,within_fixture_voltage_window=dc-peak>=2.5 and dc+peak<=3.6))
    return dict(cases=rows,complete=False,
        scope='Assigned RLC grid and 7 pC H2D stress; not a measured or exhaustive tolerance envelope. Timing uses assigned 0.1 ps/mV, 1 GHz pole. No payload quality qualification.',
        limitations=['Series lumped capacitor only; distributed coupling and broadband random switching omitted.',
            'Only nominal carriers and six D2H harmonics; no full carrier sweep or resonance qualification.',
            'Plate area omits layout overhead; density option and actual ESR/ESL remain unverified.',
            'Shared 2 ohm local branch remains hypothetical; baseline unchanged.'])


def periodic_phase_spurs(carrier_hz,tones,*,refinement=1):
    """Exact sampled exp(j*phase) for commensurate host tones, not small-angle PM.

    The ideal 2.400–2.484 GHz filter is an optimistic projection only. Its
    surviving sidebands cannot be removed by improving its out-of-band stopband.
    """
    if not tones or refinement not in (1,2):raise ValueError('Explicit periodic tones and bounded refinement required')
    if not math.isfinite(carrier_hz) or carrier_hz<=0:raise ValueError('Positive finite RF carrier required')
    frequencies=[]
    for f,a,p in tones:
        if not all(math.isfinite(v) for v in (f,a,p)) or f<=0:
            raise ValueError('Finite positive periodic host tones required')
        rational=Fraction(str(f)).limit_denominator(1024)
        if abs(float(rational)-f)>1e-6:raise ValueError('Host tones need a bounded rational-Hz grid')
        frequencies.append(rational)
    denominator=math.lcm(*(f.denominator for f in frequencies))
    fundamental=float(Fraction(math.gcd(*(int(f*denominator) for f in frequencies)),denominator))
    count=max(256,2**math.ceil(math.log2(8*max(frequencies)/fundamental)))*refinement
    if count>2**20:raise ValueError('Periodic screen grid too large; use a different frequency-domain reduction')
    times=np.arange(count)/(count*fundamental)
    phase=sum(a*np.cos(2*math.pi*f*times+p) for f,a,p in tones)
    spectrum=abs(np.fft.fft(np.exp(1j*phase))/count)**2
    offsets=np.fft.fftfreq(count,1/(count*fundamental))
    noncarrier=offsets!=0
    passband=(carrier_hz+offsets>=2.4e9)&(carrier_hz+offsets<=2.484e9)
    surviving=noncarrier&passband
    peaks=np.flatnonzero(surviving)
    peaks=sorted(peaks,key=lambda k:spectrum[k],reverse=True)[:5]
    center=float(spectrum[0]);retained=float(np.sum(spectrum[surviving]))
    return dict(carrier_hz=carrier_hz,samples=count,fundamental_hz=fundamental,
        resolved_offset_limit_hz=count*fundamental/2,
        total_power_fraction=float(np.sum(spectrum)),carrier_power_fraction=center,
        ideal_band_filter_retained_unwanted_fraction=retained,
        retained_unwanted_to_carrier=retained/center,
        rejectable_outside_band_fraction=float(np.sum(spectrum[~passband])),
        beyond_40mhz_fraction=float(np.sum(spectrum[abs(offsets)>=40e6])),
        strongest_retained_lines=[dict(offset_hz=float(offsets[k]),rf_hz=float(carrier_hz+offsets[k]),
            power_fraction=float(spectrum[k]),dbc=10*math.log10(max(float(spectrum[k])/center,1e-300))) for k in peaks],
        scope='Supply-induced periodic phase on a unit carrier, including nonlinear mixing of tones. Ideal rectangular full-band filter, no modulation bandwidth or actual filter loss; not an emission mask or physical isolation claim.')


def tx_clock_spur_envelope(contract):
    rows=[]
    # Full /16 and reduced /32 are existing candidates. /24 is a numerical
    # intermediate-divider investigation, not an allocated/implemented clock.
    for divider in (16,24,32):
        for charge in (.3e-12,7e-12):
            for carrier in range(2400000000,2484000001,2000000):
                env=operating_environment(contract,shared_board_candidate(),carrier_hz=carrier,
                    d2h_word_hz=2*carrier/divider,payload_engine='rf',payload_current_a=.037,
                    h2d_internal_charge_c=charge,d2h_harmonics=3*divider//8)
                tones=[(t['frequency_hz'],-2*math.pi*carrier*t['delay_peak_s'],t['delay_phase_rad'])
                    for t in env['supply_delay']['tones']]
                spectrum=periodic_phase_spurs(carrier,tones)
                rail=env['ledger']['local_payload_clock_core_rail_v']
                peak=sum(t['clock_rail_voltage_peak_v'] for t in env['host_spectrum']['tones'])
                rows.append(dict(d2h_clock_divider=divider,h2d_internal_charge_c=charge,
                    spectrum=spectrum,phase_tones=tones,
                    total_assigned_current_a=env['ledger']['total_chip_supply_current_a'],
                    conservative_rail_interval_v=[rail-peak,rail+peak],
                    linear_fixture_voltage_range_guaranteed=rail-peak>=2.5 and rail+peak<=3.6))
    decisions=[]
    for divider in (16,24,32):
        for charge in (.3e-12,7e-12):
            selected=[r for r in rows if r['d2h_clock_divider']==divider and r['h2d_internal_charge_c']==charge]
            worst=max(selected,key=lambda r:r['spectrum']['retained_unwanted_to_carrier'])
            reference=worst['spectrum'];tones=worst['phase_tones']
            refined=periodic_phase_spurs(reference['carrier_hz'],tones,refinement=2)
            # Inverse requirement only for the selected worst sampled carrier;
            # -40 dBc aggregate is an illustrative allocation, not a standard.
            low=0.;high=1.
            for _ in range(18):
                mid=(low+high)/2
                q=periodic_phase_spurs(reference['carrier_hz'],[(f,a*mid,p) for f,a,p in tones])
                if q['retained_unwanted_to_carrier']<=1e-4:low=mid
                else:high=mid
            decisions.append(dict(d2h_clock_divider=divider,h2d_internal_charge_c=charge,
                worst_sampled_carrier_hz=reference['carrier_hz'],
                worst_retained_unwanted_to_carrier=reference['retained_unwanted_to_carrier'],
                strongest_retained_lines=reference['strongest_retained_lines'],
                assigned_current_range_a=[min(r['total_assigned_current_a'] for r in selected),max(r['total_assigned_current_a'] for r in selected)],
                every_sampled_rail_interval_guaranteed=all(r['linear_fixture_voltage_range_guaranteed'] for r in selected),
                illustrative_retained_power_allocation=1e-4,
                selected_carrier_maximum_tested_passing_sensitivity_ps_per_mv=.1*low,
                inverse_search_capped_at_assigned_sensitivity=low>1-1e-4,
                refinement_absolute_retained_power_change=abs(reference['retained_unwanted_to_carrier']-refined['retained_unwanted_to_carrier'])))
    for r in rows:
        del r['phase_tones']
        r['spectrum'].pop('scope')
        peaks=r['spectrum'].pop('strongest_retained_lines')
        r['spectrum']['strongest_retained_line']=peaks[0] if peaks else None
    return dict(cases=rows,comparisons=decisions,complete=False,
        status='carrier_range_clock_spur_requirements',
        assumptions=['Same shared network, bidirectional host currents and 0.1 ps/mV / 1 GHz supply-delay hypothesis as the packet environment.',
            '2 MHz carrier grid across the requested LO interval; continuous tuning and package-parameter bounds are not certified.',
            'Equal modeled D2H bandwidth (0.375 times LO); unchanged H2D tones through 937.5 MHz. Random continuous host spectra and payload current modulation remain omitted.',
            'Only supply-derived phase included: source phase noise, DAC/reference errors, IQ imbalance and output-stage noise are not replaced by this attribution.',
            'Ideal fixed full-band filter rejects everything outside 2.400–2.484 GHz and nothing inside. Modulated signals broaden lines; real filters add transition bands, insertion loss and reflections.',
            'Intermediate /24 D2H clock is an investigation requiring actual divider/source ownership, power/noise and transport closure before adoption.',
            'Inverse sensitivity applies to the worst carrier sampled at the assigned sensitivity, with other parameters fixed; not a process-performance bound or standards limit.'])


def shared_packet_lifecycle(contract):
    from ble_packet import joined_scan_request, response_budget, transmitted_scan_response
    environments={};rows=[]
    candidates=[(f'h2d_charge_{charge:g}',shared_board_candidate(),charge) for charge in (.3e-12,7e-12)]
    mitigated=shared_board_candidate()
    mitigated['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
    candidates.append(('local_500pf_adverse_h2d',mitigated,7e-12))
    for key,candidate,charge in candidates:
        env=operating_environment(contract,candidate,carrier_hz=2.426e9,
            d2h_word_hz=2.426e9/16,payload_engine='rf',payload_current_a=.037,
            h2d_internal_charge_c=charge,d2h_harmonics=12,
            reference_fraction_per_v=.1,reference_pole_hz=10e6)
        environments[key]=env
        for wanted,blocker in ((-80.,-40.),(-90.,-40.),(-90.,None)):
            for seed in (17,81,203):
                received=joined_scan_request(env,contract,seed=seed,wanted_dbm=wanted,blocker_dbm=blocker)
                received['transmission']=transmitted_scan_response(received,env,contract)
                rows.append(dict(environment=key,**received))
    attribution=[]
    for name,changes in (
            ('baseline',{}),('thermal_noise_removed_control',dict(thermal_noise_enabled=False)),
            ('adc_noise_removed_control',dict(adc_noise_enabled=False)),
            ('nf_6db_requirement',dict(noise_figure_db=6.)),
            ('adc_10enob_requirement',dict(adc_enob=10.)),
            ('initial_gain_60db_requirement',dict(initial_gain_db=60.))):
        for blocker in (None,-40.):
            trials=[joined_scan_request(environments['local_500pf_adverse_h2d'],contract,
                seed=seed,wanted_dbm=-90.,blocker_dbm=blocker,**changes) for seed in (17,81,203)]
            attribution.append(dict(change=name,parameters=changes,blocker_dbm=blocker,
                acquired=sum(x['observation']['acquired'] for x in trials),
                correct_requests=sum(x['correct_request'] for x in trials),
                trials=[dict(seed=x['seed'],correct_request=x['correct_request'],
                    observation=x['observation'],gain_control=x['gain_control']) for x in trials]))
    filter_trials=[]
    for cutoff in (.475e6,.5e6,.525e6):
        for seed in (317,401,509,613,719,827):
            trial=joined_scan_request(environments['local_500pf_adverse_h2d'],contract,
                seed=seed,wanted_dbm=-90.,blocker_dbm=-40.,noise_figure_db=6.,rx_cutoff_hz=cutoff)
            filter_trials.append(dict(cutoff_hz=cutoff,**trial))
    linearity_trials=[]
    for intercept in (None,-20.,-10.,0.):
        for seed in (17,81,203):
            trial=joined_scan_request(environments['local_500pf_adverse_h2d'],contract,
                seed=seed,wanted_dbm=-80.,blocker_dbm=-30.,noise_figure_db=6.,rx_cutoff_hz=.5e6,
                blocker_offsets_hz=(2e6,4e6),input_iip3_dbm=intercept)
            linearity_trials.append(dict(input_iip3_dbm=intercept,**trial))
    nominal=environments['h2d_charge_3e-13']
    refinement=[joined_scan_request(nominal,contract,include_noise=False,mixer_substeps=n)
        for n in (256,512)]
    first=next(r for r in rows if r['environment']=='h2d_charge_3e-13' and r['correct_request'])
    late=response_budget(first['observation'],first['settings'],nominal,contract,
        advertiser_address=bytes.fromhex('a6a5a4a3a2c1'),fpga_work_s=160e-6)
    return dict(environments=environments,cases=rows,
        frontend_linearity=dict(environment='local_500pf_adverse_h2d',cases=linearity_trials,
            scope='Two equal-power external blockers at +2/+4 MHz; cubic IM3 lands at wanted carrier. Delivered-clock comparison isolates frontend linearity; not the loaded-clock envelope. Constant NF/current versus IIP3 is an unpriced hypothesis; polynomial-invalid cases cannot qualify performance.'),
        weak_signal_attribution=dict(environment='local_500pf_adverse_h2d',wanted_dbm=-90.,cases=attribution,
            scope='One-factor hypotheses at fixed supply/clock/reference/gain limits. Noise removal is nonphysical attribution; NF/ENOB changes have unpriced circuit costs. Three seeds do not establish PER.'),
        filter_retuning=dict(environment='local_500pf_adverse_h2d',noise_figure_db=6.,cases=filter_trials,
            representative_reply=transmitted_scan_response(next(x for x in filter_trials if x['cutoff_hz']==.5e6 and x['seed']==317),environments['local_500pf_adverse_h2d'],contract),
            scope='Existing five-stage filter; independent held-out seeds at selected cutoff and +/-5 percent. No added stages. NF and filter precision/current remain hypotheses; no PER confidence or mask qualification.'),
        additive_noise_disabled_mixer_refinement=refinement,
        additive_noise_disabled_weak_control=joined_scan_request(nominal,contract,wanted_dbm=-90.,blocker_dbm=None,include_noise=False),
        late_host_control=late,
        fixed_timing_correction_controls=[dict(seed=r['seed'],**transmitted_scan_response(r,nominal,contract,
            rx_timestamp_correction_s=.8e-6,tx_launch_advance_s=.15e-6)) for r in rows
            if r['environment']=='h2d_charge_3e-13' and r['correct_request']],
        host_stall_control=transmitted_scan_response(first,nominal,contract,host_gap_s=10e-6),
        tx_refinement_control=transmitted_scan_response(first,nominal,contract,mixer_substeps=512),
        complete=False,status='shared_environment_packet_exchange_conditional',
        protocol_reference='https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/low-energy-controller/link-layer-specification.html',
        assumptions=['External FPGA parses LE 1M channel-38 SCAN_REQ, CRC and advertiser address; no chip protocol profile or CRC engine.',
            'Already inside a valid scannable advertising receive window. Preceding advertisement and scanner state machine are not simulated.',
            '2 dB external insertion loss for both wanted and the adjacent 2 MHz blocker: no free external adjacent-channel rejection.',
            '10 dB NF, 20 dB early gain, bounded 0–60 dB main PGA, 8 ENOB and rail-proportional gain/headroom are assigned requirements, not GF180 measurements.',
            'The same source phase drives mixer and divided ADC crossings; reference ripple reaches quantization. Thermal noise has fixed input-referred density before filtering.',
            'FIFO service bounds, 64-tap FPGA resampler lookahead, command framing, CDC, settling and bounded sample prefill are charged to response preparation.',
            '150 us is the fixed primary-advertising inter-frame spacing, not a channel-retune allowance. LO/sample/host clocks and stream epoch remain running.',
            'Finite timestamped DAC playback now emits a loaded reply through the shared clock/reference environment to an independent strong-signal peer. Arrival times still assume the bounded host service, not the implemented bridge.',
            'Static response samples reside in FPGA memory; a 32-sample prefill is held on-chip until launch. Clock phase continues across RX, wait and TX. Underflow latches mute.',
            'Fixed 0.8 us RX and 0.15 us TX timing corrections are hypotheses, not fitted per packet or physically calibrated. Half-amplitude RF start is a diagnostic marker, not a standards timing verdict.',
            'TX uses existing assigned IQ/compression parameters, 40 ohm source and 50 ohm load, with 28 mA driver reservation already inside the 37 mA RF allowance. TX-load PDN feedback and emission limits remain open.',
            'Three packet seeds per point do not establish PER, sensitivity or standards compliance.'])


def loaded_clock_packet_exchange(contract):
    """Paired complete exchange: same RF/PDN, delivered vs loaded clock input."""
    from ble_packet import joined_scan_request,transmitted_scan_response
    environments={};rows=[]
    candidate=shared_board_candidate()
    candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
    for name,options in (('ideal_delivered',None),('high_impedance',dict(termination_ohm=None)),
                         ('terminated_50ohm',dict(termination_ohm=50.)),
                         ('quiet_high_impedance_requirement',dict(termination_ohm=None,receiver_noise_v=.25e-3,downstream_stage_rms_s=.05e-12)),
                         ('quiet_terminated_requirement',dict(termination_ohm=50.,receiver_noise_v=.25e-3,downstream_stage_rms_s=.05e-12)),
                         ('lower_noise_high_impedance_requirement',dict(termination_ohm=None,receiver_noise_v=.075e-3,downstream_stage_rms_s=.015e-12)),
                         ('lower_noise_terminated_requirement',dict(termination_ohm=50.,receiver_noise_v=.075e-3,downstream_stage_rms_s=.015e-12))):
        env=operating_environment(contract,candidate,carrier_hz=2.426e9,
            d2h_word_hz=2.426e9/16,payload_engine='rf',payload_current_a=.037,
            h2d_internal_charge_c=7e-12,d2h_harmonics=12,
            reference_fraction_per_v=.1,reference_pole_hz=10e6,external_input=options)
        environments[name]=env
        for seed in (317,401,509,613,719,827):
            received=joined_scan_request(env,contract,seed=seed,wanted_dbm=-90.,
                blocker_dbm=-40.,noise_figure_db=6.,rx_cutoff_hz=.5e6)
            transmission=transmitted_scan_response(received,env,contract)
            rows.append(dict(environment=name,received=received,transmission=transmission))
    moderate=[]
    for name in ('high_impedance','terminated_50ohm'):
        for seed in (317,401,509,613,719,827):
            received=joined_scan_request(environments[name],contract,seed=seed,
                wanted_dbm=-80.,blocker_dbm=-40.)
            moderate.append(dict(environment=name,received=received))
    combined=[]
    for name in ('ideal_delivered','quiet_high_impedance_requirement','quiet_terminated_requirement',
                 'lower_noise_high_impedance_requirement','lower_noise_terminated_requirement'):
        for seed in (317,401,509,613,719,827):
            received=joined_scan_request(environments[name],contract,seed=seed,wanted_dbm=-80.,
                blocker_dbm=-30.,noise_figure_db=6.,rx_cutoff_hz=.5e6,
                blocker_offsets_hz=(2e6,4e6),input_iip3_dbm=0.)
            combined.append(dict(environment=name,received=received,
                transmission=transmitted_scan_response(received,environments[name],contract)))
    return dict(environments=environments,cases=rows,moderate_signal_controls=moderate,
        combined_frontend=combined,complete=False,
        scope='Same six packet seeds, wanted/blocker, PDN, NF, cutoff, host service and driver hypotheses. Source/input phase persists across reception and reply.',
        limitations=['Only one carrier and candidate input load; finite observations do not establish PER or voltage/phase tolerance.',
            'Source/input random band 1 kHz–8 MHz; phase sideband dispersion and correlated noise omitted.',
            '6 dB NF, input receiver and local decoupling have unqualified current/area costs.',
            'Combined frontend cases use 0 dBm IIP3 with -80 dBm wanted and two -30 dBm blockers; simultaneous noise/linearity/current remains a requirement, not a demonstrated circuit.',
            'No static input propagation delay or calibrated RF launch; diagnostic amplitude marker is not protocol timing qualification.',
            'TX spectral bands are broad integrals before external filtering, not emission masks.'])


def whole_chip_operating_envelopes(contract):
    """Compare exclusive payload modes without changing the board assumptions.

    Explicit environments, not independently selected RF/wired corners.
    The 1 uF case matches a Run 1 footprint value, not qualified impedance.
    """
    from check_contract import periodic_stream_bound
    base=next(x['rf'] for x in contract['behavioral_configuration_cases'] if x['id']=='wifi_he20__40000000.0')
    rows=[];wire_scenarios=[]
    wire_allocation=sum(len(d['supply_pins'])*d['per_connection_budget_ma']*1e-3
        for d in contract['power']['domains'] if d['id']=='WIRE')
    configurations=[]
    for cap in (1e-6,10e-6):
        for charge in (.3e-12,7e-12):
            configurations.append((f'board_{cap:g}_h2d_charge_{charge:g}',shared_board_candidate(cap),charge,None))
    for esr,esl in ((.5,200e-12),(1.,1e-9)):
        candidate=shared_board_candidate()
        candidate['network'].update(die_c=500e-12,die_esr=esr,die_esl=esl)
        configurations.append((f'local_500pf_esr_{esr:g}_esl_{esl:g}',candidate,7e-12,None))
    for termination in (None,50.):
        candidate=shared_board_candidate()
        candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        configurations.append((f'loaded_input_termination_{termination}',candidate,7e-12,dict(termination_ohm=termination)))
    for case_id,candidate,charge,input_options in configurations:
        modes={}
        for engine,carrier,word,current,harmonics in (
            ('rf',2.437e9,2.437e9/16,.037,12),
            ('wire',2.5e9,312.5e6,wire_allocation,6)):
            env=operating_environment(contract,candidate,carrier_hz=carrier,
                d2h_word_hz=word,payload_engine=engine,payload_current_a=current,
                h2d_internal_charge_c=charge,d2h_harmonics=harmonics,external_input=input_options,
                reference_fraction_per_v=.1,reference_pole_hz=10e6)
            rail=env['ledger']['local_payload_clock_core_rail_v']
            peak=sum(t['clock_rail_voltage_peak_v'] for t in env['host_spectrum']['tones'])
            env['conservative_local_rail_interval_v']=[rail-peak,rail+peak]
            env['assigned_linear_fixture_voltage_range_v']=[2.5,3.6]
            env['linear_fixture_voltage_range_guaranteed']=(rail-peak>=2.5 and rail+peak<=3.6)
            # Clock and payload reservations are assigned; wire uses its full
            # planning ceiling to expose shared-feed cost, not measured draw.
            arrival=carrier/64 if engine=='rf' else carrier/10
            t=contract['transport']
            env['transport']=periodic_stream_bound(arrival_item_hz=arrival*(1+t['source_fast_ppm']/1e6),
                item_bits=24 if engine=='rf' else 10,word_hz=word*(1-t['host_slow_ppm']/1e6),
                frame_words=t['frame_words'],payload_words=t['frame_words']-t['control_words'],
                staging_frames=t['scheduling']['staging_frames'],cdc_words=2)
            if engine=='rf':
                phase=PhaseNoise(tuple(env['delivered_phase_tones']))
                q=waveform_screen(fixture('wifi_he20',seed=81),replace(Assumptions(),
                    converter_enob=8.,frontend_evm_rms=.04,relative_lo_phase_rms_rad=0.,sample_jitter_s=.3e-12),
                    {'estimated_rail_v':{'RF':rail}},settings=external_settings(base,carrier),
                    recover_carrier=True,fpga_resampling=True,blocker=dict(offset_hz=12e6,relative_power_db=2.),
                    frontend_loss_db=2.,frontend_saturation_v=2.,pga_peak_limit_v=.8*rail/3.3,
                    mixer_phase_noise=phase,sample_phase_noise=phase,mixer_substeps=128,
                    adc_reference_scale=lambda times:environment_reference_scale(env,times))
                env['receiver']=summarize_quality(q)
            else:
                wire_scenarios.append(dict(name=case_id,delay_tones=env['crossing_delay_tones'],
                    signal_scale=min(1.,rail/3.3)))
            modes[engine]=env
        rows.append(dict(configuration=case_id,modes=modes))
    wired=causal_receiver_envelope(timing_scenarios=wire_scenarios)
    for row in rows:
        cases=[c for c in wired['cases'] if c['impairment']['name']==row['configuration']]
        row['modes']['wire']['receiver']=dict(channel_cases=cases,
            heldout_errors=sum(c['heldout_errors'] for c in cases),
            zero_error_cases=sum(c['heldout_errors']==0 for c in cases),case_count=len(cases))
    return dict(cases=rows,complete=False,status='shared_environment_exclusive_mode_comparison',
        decisions=['Retain reduced RF D2H rate; wired top-rate transport still requires its higher host rate.',
            'Capacitance alone is not isolation: compare current, DC headroom, ripple and received quality together.',
            'A receiver diagnostic pass cannot establish feasibility when the declared linear fixture voltage envelope is not guaranteed.'],
        assumptions=['Same board, return, host input load and supplied source spectrum in each paired RF/wired case; payloads never active simultaneously.',
            '1 uF is an observed Run 1 footprint label, not measured populated impedance. 10 uF requires external support and modeled connection inductance.',
            '2 ohm local branch and 100 pF baseline or 500 pF candidate require an implementation behind compatible supply sites. Candidate capacitor ESR/ESL are hypotheses, not extracted bounds.',
            'Wired current equals its whole WIRE planning allocation, including locally supplied drive; it is a budget stress, not predicted draw. Externally supplied TMDS return is not modeled here.',
            'Wired signal scales linearly with its DC rail as an assigned stress. Driver compliance and sampler threshold supply response require device models.',
            'RF source spectrum, reference rejection, NF/gain/current and headroom remain conditional; RF uses synthetic acquisition and proportional noise, not a sensitivity test.',
            'Source startup/retune, true packet turnaround, live FIFO service, TX emissions and all target-specific electrical actions remain open.'])


def reference_supply_screen(contract,coupling):
    results=[]
    for feedthrough,pole in ((0.,1e9),(1.,1e9),(1.,10e6),(.1,1e9)):
        report=common_feed_rf_screen(contract,coupling,clock_sensitivity_ps_per_mv=.01,
            reference_fraction_per_v=feedthrough,reference_pole_hz=pole)
        results.extend(report['cases'])
    return dict(cases=results,complete=False,
        scope=['Same common-feed DC and directional host spectra; lower clock sensitivity isolates reference-path risk without removing clock coupling.',
            'ADC reference fraction per supply volt and first-order pole are assigned hypotheses, not measured PSRR.',
            'Reference acts at actual converter timestamps after analog filtering; receiver sees quantized codes, not the reference waveform.',
            'D2H coherent harmonics can resemble static gain; independent H2D lines can alias into baseband.',
            'Reference dynamic load, DAC reference, supply-dependent noise/linearity and circuit costs remain unqualified.'])


def rf_host_rate_comparison(contract,coupling):
    """Paired rate change with fixed LO, conversion, H2D and assigned PDN."""
    rows=[]
    for word in (2.437e9/8,2.437e9/16):
        report=common_feed_rf_screen(contract,coupling,d2h_word_hz=word,d2h_harmonics=round(6*(2.437e9/8)/word),
            clock_sensitivity_ps_per_mv=.1,reference_fraction_per_v=.1,reference_pole_hz=1e9)
        for row in report['cases']:
            row.update(d2h_word_hz=word,frame_duration_s=64/word,
                rf_sample_hz=2.437e9/64,h2d_word_hz=312.5e6,
                payload_capacity_bps=word*10*59/64,payload_demand_bps=24*2.437e9/64)
            rows.append(row)
    return dict(cases=rows,complete=False,status='paired_host_rate_dc_spectral_rx_comparison',
        limitations=['Both rates use identical assigned network, source phase noise, RF settings and H2D activity.',
            'Same D2H bandwidth through 913.875 MHz: six harmonics at full rate, twelve at half rate. H2D remains through 937.5 MHz; stochastic activity and higher frequencies remain omitted.',
            'Reference coupling 0.1 fraction/V and clock sensitivity 0.1 ps/mV with 1 GHz poles are hypotheses.',
            'Dense sample transport capacity is checked separately; waveform fixture does not exercise slower live transport or turnaround.',
            'Reduced output switching is not proof of lower total analog impairment or a physically qualified divider.'])


def absolute_rf_screen(contract,coupling):
    """Replace proportional frontend noise with a declared matched-input budget.

    Gain is an inverse requirement maintaining the existing signal scale; no
    claim that the physical gain control can provide this range is made.
    """
    rows=[]
    amplitude=10**(-Assumptions().converter_backoff_db/20)
    for signal_dbm in (-65.,-75.,-85.):
        input_w=1e-3*10**(signal_dbm/10)
        gain_db=20*math.log10(amplitude/math.sqrt(2*50*input_w))
        budget=rf_receiver_electrical_budget(temperature_k=300.15,noise_bandwidth_hz=20e6,
            noise_figure_db=10.,conversion_voltage_gain_db=gain_db,
            volts_per_normalized_unit=1.,signal_normalized_rms=amplitude)
        result=common_feed_rf_screen(contract,coupling,d2h_word_hz=2.437e9/16,d2h_harmonics=12,
            clock_sensitivity_ps_per_mv=.1,reference_fraction_per_v=.1,
            frontend_evm_rms=budget['frontend_evm_rms'])
        for row in result['cases']:
            row.update(antenna_wanted_dbm=signal_dbm,antenna_blocker_dbm=signal_dbm+20,
                wanted_filter_loss_db=2.,blocker_filter_attenuation_db=20.,
                required_conversion_voltage_gain_db=gain_db,electrical_noise_budget=budget,
                noise_only_evm_after_insertion_loss=budget['frontend_evm_rms']*10**(2/20))
            rows.append(row)
    return dict(cases=rows,complete=False,status='absolute_input_noise_hypothesis_not_sensitivity_qualification',
        assumptions=['Matched 50 ohm antenna plane, 300.15 K, assigned receiver NF 10 dB and ENBW 20 MHz.',
            'Passive preselection at the same temperature: 2 dB wanted loss, 20 dB blocker attenuation, blocker +20 dB at 12 MHz offset before filtering.',
            'Complex RF envelope power is E|z|^2/(2R); 1 V per normalized unit is an assigned conversion-output scale.',
            'Required conversion gain is independently reset per signal level to preserve existing normalized signal amplitude; physical gain range, AGC dynamics, power, headroom and NF versus gain remain open.',
            'Integrated thermal noise enters after receive filtering and before ADC quantization; it remains a white equivalent-noise approximation, not a colored device-noise waveform.',
            'Same half-rate D2H, fixed conversion/H2D, reference coupling and host-supply spectra as paired mitigation study.',
            'Synthetic training and BPSK fixture do not establish packet sensitivity, blocker compliance or useful higher MCS.'])


def rf_gain_headroom_budget(*,wanted_dbm,blocker_dbm,wanted_loss_db,
                           blocker_attenuation_db,blocker_offset_hz,cutoff_hz,
                           filter_order,enob,adc_noise_evm_limit,component_peak_limit_v,
                           wanted_peak_to_rms=3.):
    """Inverse gain interval at the ADC, with an explicit blocker rejection.

    Continuous Butterworth magnitude matches the selected filter hypothesis.
    ADC spans +/-1 V per component. No LNA/mixer/internal-filter headroom proof.
    """
    values=(wanted_dbm,blocker_dbm,wanted_loss_db,blocker_attenuation_db,blocker_offset_hz,
            cutoff_hz,enob,adc_noise_evm_limit,component_peak_limit_v,wanted_peak_to_rms)
    if not all(math.isfinite(v) for v in values) or min(cutoff_hz,enob,adc_noise_evm_limit,component_peak_limit_v,wanted_peak_to_rms)<=0 or min(wanted_loss_db,blocker_attenuation_db,blocker_offset_hz)<0 or type(filter_order) is not int or filter_order<1:
        raise ValueError('Finite positive gain/headroom requirements required')
    rejection_db=10*math.log10(1+(blocker_offset_hz/cutoff_hz)**(2*filter_order))
    ratio=10**((blocker_dbm-blocker_attenuation_db-rejection_db-(wanted_dbm-wanted_loss_db))/20)
    # Complex RMS of independent per-component equivalent quantization noise.
    adc_noise=2**(1-enob)/math.sqrt(6)
    minimum_signal=adc_noise/adc_noise_evm_limit
    maximum_signal=component_peak_limit_v/(wanted_peak_to_rms+ratio)
    input_envelope=math.sqrt(2*50*1e-3*10**((wanted_dbm-wanted_loss_db)/10))
    allowable_ratio=component_peak_limit_v/minimum_signal-wanted_peak_to_rms
    needed_rejection=(max(0.,blocker_dbm-(wanted_dbm-wanted_loss_db)-20*math.log10(allowable_ratio))
                      if allowable_ratio>0 else None)
    return dict(wanted_dbm=wanted_dbm,blocker_dbm=blocker_dbm,
        filter_rejection_db=rejection_db,external_blocker_attenuation_db=blocker_attenuation_db,
        external_wanted_loss_db=wanted_loss_db,
        external_selective_rejection_db=blocker_attenuation_db-wanted_loss_db,
        minimum_wanted_adc_rms_v=minimum_signal,maximum_wanted_adc_rms_v=maximum_signal,
        minimum_voltage_gain_db=20*math.log10(minimum_signal/input_envelope),
        maximum_voltage_gain_db=20*math.log10(maximum_signal/input_envelope),
        gain_interval_exists=minimum_signal<=maximum_signal,
        required_total_blocker_rejection_db=needed_rejection,
        additional_rejection_needed_db=None if needed_rejection is None else max(0.,needed_rejection-blocker_attenuation_db-rejection_db),
        enob=enob,adc_noise_evm_limit=adc_noise_evm_limit,
        scope='Necessary ADC-noise/headroom compatibility under assigned filter and crest factor, not complete sensitivity or linearity proof')


def rf_gain_headroom_requirements():
    return dict(cases=[rf_gain_headroom_budget(wanted_dbm=w,blocker_dbm=b,wanted_loss_db=2.,
        blocker_attenuation_db=attenuation,blocker_offset_hz=12e6,cutoff_hz=9.157407e6,
        filter_order=5,enob=n,adc_noise_evm_limit=.05,component_peak_limit_v=.8)
        for attenuation in (2.,20.) for w in (-65.,-75.,-85.)
        for b in (w+20.,-30.) for n in (8.,10.)],complete=False,
        limitations=['The 2 dB external case attenuates wanted and blocker equally: no selective external rejection. The historical 20 dB blocker case assumes 18 dB selective rejection beyond wanted insertion loss; availability at 12 MHz offset is unproven.',
            'Wanted internal-filter passband attenuation is omitted; all values are assigned requirements, not measured ranges.',
            'Wanted component peaks are bounded by three times complex RMS; a CW blocker uses its complex envelope amplitude.',
            'Gain after filtering can protect the PGA/ADC but cannot prevent earlier LNA, mixer or filter internal-node compression.',
            'NF, reciprocal mixing, AGC settling and gain-dependent current remain separate conditions; a nonempty gain interval is not a radio pass.'])


def wideband_filter_waveform(*,oversample=16):
    """Persistent analog filtering of the existing HE20 DATA fixture.

    First known DATA symbol trains one complex coefficient per occupied data
    tone in an external observer. Ideal boundaries, no standard preamble.
    """
    from scipy import signal
    from protocol_signals import he20
    if type(oversample) is not int or oversample<4:
        raise ValueError('Integer envelope oversampling of at least four required')
    bits=np.random.default_rng(431).integers(0,2,234*24)
    rows=[]
    for gi in (.8,1.6,3.2):
        w=he20(bits,gi_us=gi);cp=w.metadata['cp'];bins=np.array(w.metadata['data'])%256
        frames=np.asarray(w.samples).reshape(-1,256+cp)
        spectrum=np.fft.fft(frames[:,cp:],axis=1)
        padded=np.zeros((len(frames),256*oversample),complex)
        padded[:,:128]=spectrum[:,:128];padded[:,-128:]=spectrum[:,-128:]
        high=np.fft.ifft(padded,axis=1)*oversample
        drive=np.concatenate([np.r_[row[-cp*oversample:],row] for row in high])
        for kind in ('butterworth_control','finite_zero_candidate'):
            if kind=='butterworth_control':
                b,a=signal.butter(5,1,analog=True);cutoff=9.157407e6
            else:
                b,a=signal.ellip(5,1,36.40776933523119,1,analog=True);cutoff=9.53125e6
            residues,poles,direct=signal.residue(b,a)
            if len(direct):raise ValueError('Strictly proper candidate required')
            exponent=poles*2*math.pi*cutoff/(20e6*oversample)
            decay=np.exp(exponent);feed=np.expm1(exponent)/poles
            # Same exact-ZOH modal update as MultipoleEnvelope, continuous
            # across every symbol. High-rate source is held between substeps.
            output=sum(r*signal.lfilter([f],[1,-d],drive) for r,f,d in zip(residues,feed,decay))
            observed=output[oversample-1::oversample].reshape(frames.shape)
            y=np.fft.fft(observed[:,cp:],axis=1)[:,bins];x=spectrum[:,bins]
            equalizer=y[0]/x[0]
            common=np.vdot(x[0],y[0])/np.vdot(x[0],x[0])
            corrected=y[1:]/equalizer
            evm=lambda z:float(np.sqrt(np.mean(abs(z-x[1:])**2)/np.mean(abs(x[1:])**2)))
            rows.append(dict(filter=kind,guard_interval_s=gi*1e-6,
                known_training_per_tone_evm=evm(corrected),common_only_evm=evm(y[1:]/common),
                bpsk_errors_after_equalization=int(np.sum((corrected.real>0)!=(x[1:].real>0))),
                evaluated_data_bits=int(x[1:].size),
                maximum_equalizer_voltage_gain=float(max(1/abs(equalizer)))))
    return dict(cases=rows,oversample=oversample,training_symbols=1,payload_symbols=23,complete=False,
        scope='Noiseless bandwidth/delay compatibility only. Known DATA training and ideal symbol boundaries are explicitly not real protocol acquisition. No blockers, converter quantization, absolute RF noise/gain/headroom, loaded timing, mismatch, clipping or internal-node swing. The trained external per-tone equalizer is a requirement, not implemented FPGA logic. Filter memory persists across symbols; longer guard cases are alternatives, not replacements for the shortest guard.')


def wideband_filter_requirements():
    """Magnitude-only alternatives preserving the existing HE20 fixture tones.

    Conservative per-tone desired-amplitude bound, not integrated OFDM EVM.
    Coefficients are ideal analog transfer functions, not GF180 circuits.
    """
    from scipy import signal
    wanted_edge=122*20e6/256
    blocker=12e6;passband_loss=1.
    rows=[]
    for bits in (8,10):
        adc_noise=2**(1-bits)/math.sqrt(6)
        allowed_ratio=.8/(adc_noise/.05)-3.
        # Both RF inputs see the same 2 dB insertion loss. Require the full
        # 55 dB antenna separation to fit, including worst wanted filter loss.
        base_rejection=55-20*math.log10(allowed_ratio)
        required=base_rejection+passband_loss
        butter_order=math.ceil(math.log10((10**(required/10)-1)/(10**(passband_loss/10)-1)) /
            (2*math.log10(blocker/wanted_edge)))
        order,wn=signal.ellipord(2*math.pi*wanted_edge,2*math.pi*blocker,
            passband_loss,required,analog=True)
        z,p,k=signal.ellip(order,passband_loss,required,wn,analog=True,output='zpk')
        frequency=np.linspace(0,wanted_edge,10001);omega=2*math.pi*frequency
        variations=[]
        for scale in (.98,1.,1.02):
            zs,ps,ks=z*scale,p*scale,k*scale**(len(p)-len(z))
            _,h=signal.freqs_zpk(zs,ps,ks,omega)
            _,hb=signal.freqs_zpk(zs,ps,ks,[2*math.pi*blocker])
            loss=float(-20*np.log10(min(abs(h))))
            rejection=float(-20*np.log10(abs(hb[0])))
            delay=-np.gradient(np.unwrap(np.angle(h)),omega)
            variations.append(dict(frequency_scale=scale,worst_passband_loss_db=loss,
                blocker_rejection_db=rejection,required_rejection_with_actual_loss_db=base_rejection+loss,
                conservative_headroom_margin_db=rejection-base_rejection-loss,
                passband_group_delay_min_s=float(min(delay)),passband_group_delay_max_s=float(max(delay)),
                magnitude_requirement_met=loss<=passband_loss+1e-9 and rejection>=base_rejection+loss))
        rows.append(dict(enob=bits,butterworth_minimum_order=butter_order,
            elliptic_order=int(order),required_blocker_rejection_db=required,
            finite_zero_frequencies_hz=sorted({float(abs(v.imag)/(2*math.pi)) for v in z}),
            maximum_pole_q=float(max(abs(p)/(-2*p.real))),variations=variations))
    return dict(wanted_edge_hz=wanted_edge,blocker_offset_hz=blocker,
        wanted_dbm=-85.,blocker_dbm=-30.,external_selective_rejection_db=0.,
        passband_loss_limit_db=passband_loss,adc_noise_evm_allocation=.05,
        cases=rows,complete=False,
        scope='Ideal filter requirements only. Edge comes from the existing 256-point/20 MS/s fixture, not a new standards claim. One dB passband loss is an investigation allocation. Neither thermal noise, early compression, internal filter swing, group-delay equalization, real-preamble acquisition, TX/RX recovery nor circuit power/area is demonstrated. Uniform frequency scaling is a sensitivity probe; independent pole/zero/Q mismatch is untested. High Q and zeros require tunable realizable circuitry; no free extra stages, external filter credit or narrower wanted spectrum.')


def periodic_reference_droop(times,*,period_s,events,resistance_ohm,capacitance_f):
    """Exact periodic steady-state RC response to signed charge impulses.

    Events are (time within period, charge drawn). This is finite output
    impedance/recovery, independent of supply PSRR; no ideal reference reset.
    """
    times=np.asarray(times,float)
    if not np.all(np.isfinite(times)) or not all(math.isfinite(v) and v>0 for v in (period_s,resistance_ohm,capacitance_f)):
        raise ValueError('Finite positive periodic reference network required')
    tau=resistance_ohm*capacitance_f;denominator=-math.expm1(-period_s/tau)
    drop=np.zeros_like(times)
    for offset,charge in events:
        if not math.isfinite(offset) or not math.isfinite(charge) or not 0<=offset<period_s:
            raise ValueError('Finite charge events within the period required')
        age=np.remainder(times-offset,period_s)
        age=np.where(np.isclose(age,period_s,rtol=0,atol=period_s*1e-12),0.,age)
        drop+=charge/capacitance_f*np.exp(-age/tau)/denominator
    return drop


def reference_load_requirements():
    fs=2.437e9/64;period=1/fs;bit_time=period/10;bits=8
    rows=[]
    for msb_charge in (.1e-12,.5e-12,2.56e-12):
        for capacitance in (20e-12,100e-12,500e-12):
            for resistance in (2.,10.,50.):
                for topology,offset,instances in (('shared_aligned',0.,1),('shared_staggered',bit_time/4,1),('separate_pairs',0.,2)):
                    local_channels=2 if instances==1 else 1
                    events=[(k*bit_time+ch*offset,msb_charge/(2**k)) for ch in range(local_channels) for k in range(bits)]
                    decisions=np.array([k*bit_time+ch*offset+.7*bit_time for ch in range(local_channels) for k in range(bits)])
                    kwargs=dict(period_s=period,events=events,resistance_ohm=resistance,capacitance_f=capacitance)
                    drops=periodic_reference_droop(decisions,**kwargs)
                    edge_drops=periodic_reference_droop(np.array([t for t,q in events]),**kwargs)
                    # Symmetric adverse upper-rail droop/lower-rail rise add in
                    # differential span; both physical reservoirs are charged.
                    span_error=2*float(max(abs(drops)))
                    peak_current=float(max(abs(edge_drops)))/resistance
                    mean_current=sum(q for t,q in events)/period
                    rows.append(dict(topology=topology,conversion_sample_hz=fs,decision_interval_s=bit_time,
                        decision_delay_s=.7*bit_time,conversion_phase_offset_s=offset,
                        msb_charge_per_rail_per_channel_c=msb_charge,reference_pair_instances=instances,
                        reservoir_per_rail_f=capacitance,output_resistance_per_rail_ohm=resistance,
                        worst_decision_span_error_v=span_error,half_lsb_span_budget_v=.5/(2**bits),
                        conditional_settling_pass=span_error<=.5/(2**bits),
                        peak_restore_current_per_rail_a=peak_current,
                        average_charge_current_all_rails_a=2*instances*mean_current,
                        reservoir_plate_area_lower_bound_um2=2*instances*capacitance/1.5e-15,
                        reference_span_collapse_in_impulse_model=2*float(max(edge_drops))>=1.))
    return dict(cases=rows,complete=False,status='reference_load_inverse_requirements_not_sar_qualification',
        assumptions=['Eight binary-weighted positive charge demands per channel in ten sample-clock subdivisions; assigned 70% decision delay.',
            '2.56 pC corresponds to 128*20 fF at 1 V in the older ideal CDAC candidate, not extracted switching charge. Smaller charges are architecture hypotheses.',
            'Worst symmetric upper/lower rail errors add; two physical reservoir capacitors per reference pair.',
            'Staggering moves conversion decisions only; simultaneous I/Q acquisition would require input sample holds and scheduling not implemented here.',
            '1.5 fF/um2 is an assigned MIM plate-density estimate; reported area excludes buffers, switches, routing, guards and mismatch margin.',
            'Restoring peak/average currents exclude buffer quiescent current, slew/current limits and stability; impulse model can demand unrealizable peaks.',
            'SAR comparator/DAC timing, charge signs/history, converter noise/linearity and 12-bit-format performance remain open.',
            'Supply PSRR and reference output impedance are distinct; passing this load screen does not inherit the quiet-supply mitigation.'])


def control_surface_coverage(contract):
    surface=contract['generic_control_surface'];services=surface['services']
    required=surface['external_interface_requirements']
    missing_targets=sorted({x['id'] for x in contract['protocol_profiles']}-set(required))
    if missing_targets:raise ValueError(f'Control coverage omits targets: {missing_targets}')
    rows=[]
    for target,controls in required.items():
        if len(set(controls))!=len(controls) or any(k not in services for k in controls):
            raise ValueError('Unknown or duplicate required generic control')
        unresolved=[k for k in controls if not services[k]['serialized_to_physical_verified'] or
                    services[k]['worst_case_apply_latency_s'] is None]
        rows.append(dict(target=target,required_services=controls,unresolved_services=unresolved,
            requirements_mapped=True,control_service_qualified=not unresolved,end_to_end_verified=False))
    return dict(interfaces=rows,complete=False,
        status='requirements_mapped_implementation_and_latency_gaps_explicit',
        sources=['rtl/pt_spi.sv','rtl/pt_stream_rx.sv','integration/pt_chip.sv',
                 'system_model/architecture_fast/resource_configuration.py','verification/recovery_mailbox.py'],
        limitation='Reviewed interface inventory, not proof by source-name matching; numerical application delay and per-target acceptance remain open.')


def capability_coverage(contract,configurations,observations):
    """Report where evidence stops, without treating test counts as completion."""
    recipes={c['id']:c for c in contract['behavioral_configuration_cases']}
    summaries=[]
    for recipe in sorted({c['recipe'] for c in configurations.values()}):
        for impairment in CASES:
            selected=[o for o in observations if o['impairment_case']==impairment and
                o['fpga_resampling'] and configurations[o['configuration_id']]['recipe']==recipe and
                configurations[o['configuration_id']]['clock']=='external_lo']
            if not selected:continue
            los=sorted({configurations[o['configuration_id']]['lo_hz'] for o in selected})
            passing_los=[lo for lo in los if any(o['quality']['conditional_waveform_pass'] and
                configurations[o['configuration_id']]['lo_hz']==lo for o in selected)]
            summaries.append(dict(recipe=recipe,fixture=recipes[recipe]['fixture'],
                impairment_case=impairment,tested_lo_hz=los,lo_hz_with_a_diagnostic_passing_configuration=passing_los,
                observed_evm_range=[min(o['quality']['evm_rms'] for o in selected),max(o['quality']['evm_rms'] for o in selected)],
                maximum_fixture_symbol_errors=max(o['quality']['symbol_errors'] for o in selected)))
    capabilities=[]
    profiles={p['id']:p for p in contract['protocol_profiles']}
    for target in contract['generic_control_surface']['external_interface_requirements']:
        profile=profiles.get(target)
        rf=(profile['engine']=='rf' if profile else target!='hd_sdi')
        joined={'wifi_he20':'Synthetic HE20 BPSK blocked RX and loaded spectral TX diagnostics',
            'bluetooth_le':'LE 1M addressed request, finite timed reply and independent peer; sensitivity/emission/timing gaps remain',
            'pcie_gen1':'2.5 Gb/s random-NRZ causal receiver; not PCIe link startup'}
        capabilities.append(dict(target=target,
            dedicated_legacy_fixture=profile is not None,
            quantitative_evidence=(('RF rate/precision fixture sweep' if rf else 'generic NRZ electrical/timing sweep')
                if profile else 'No dedicated target fixture in this report; control requirements mapped'),
            joined_evidence=joined.get(target),
            complete_operating_envelope=False,
            missing=(['protocol waveform/mask acceptance','independent complete TX and RX envelopes','per-capability coexistence and physical budgets'] if rf else
                     ['protocol-specific pad electrical and startup envelope','clock acquisition/hold across required traffic','sustained host/protocol service and physical budgets'])))
    return dict(capabilities=capabilities,external_lo_resampled_rf_slices=summaries,
        status='all_major_capability_envelopes_incomplete',
        scope=['Only evidence in this consolidated report is classified here; other repository diagnostics are not erased or declared absent.',
            'A passing LO entry means at least one tested configuration passes the generic fixture criterion there. It does not imply all settings, interpolation policy or continuous carrier range pass.',
            'EVM <=10% is a diagnostic threshold, not a common acceptance specification for these protocols.',
            'Waveform-specific symbol decisions and synthetic acquisition do not prove packets, interoperability, sensitivity or regulatory compliance.',
            'Whole-chip fit and observability remain open across all targets; no count of passing cases closes them.'])


def run():
    contract = json.loads((P/'spec/contract.json').read_text())
    # Preserve all different waveform/rate/precision recipes; redundant gain
    # probes remain in the main behavioral suite rather than bloating this one.
    recipes = [c for c in contract['behavioral_configuration_cases']
               if c['engine']=='rf' and not c['id'].startswith('gain_')]
    rows = []
    for case in recipes:
        wave = make_wave(case, 81)
        for label, parameters in CASES.items():
            a = replace(Assumptions(), **parameters)
            # Rail is a declared fixed comparison point. Do not present the
            # separate DC budget below as a joined dynamic supply simulation.
            power = {'estimated_rail_v': {'RF': 3.25}}
            baseline = waveform_screen(wave, a, power, settings=case['rf'],
                                       recover_carrier=True)
            rows.append(dict(recipe=case['id'], impairment_case=label,
                             clock='reference', fpga_resampling=False,
                             sample_hz=case['rf']['sample_hz'],
                             quality=summarize_quality(baseline)))
            for lo in LO_HZ:
                original = external_settings(case['rf'], lo)
                margin = external_settings(case['rf'], lo, minimum_filter_samples=3.)
                candidates=[('preserve_tier',original)]
                if margin!=original:candidates.append(('filter_sampling_margin',margin))
                for policy,settings in candidates:
                    tree = clock_host_candidate(settings, contract)
                    for resample in (False, True):
                        q = waveform_screen(wave, a, power, settings=settings,
                                            recover_carrier=True, fpga_resampling=resample)
                        rows.append(dict(recipe=case['id'], impairment_case=label,
                            clock='external_lo', clock_policy=policy,
                            lo_hz=lo, sample_hz=settings['sample_hz'],
                            settings=settings, clock_host_candidate=tree,
                            fpga_resampling=resample,
                            resampler_cost=resampler_cost(q['fixture_sample_hz'], settings['sample_hz']) if resample else None,
                            quality=summarize_quality(q)))
    # Do not assume that dividing by 64 resolves additive clock noise or power.
    # Sweep receiver/divider/phase/buffer static burden and aggregate switched C.
    power_cases=[]
    for lo in LO_HZ:
        for bias, cap in ((.012, 1.5e-12), (.024, 3e-12), (.036, 3e-12)):
            pll_current = bias + cap * 3.3 * lo
            a = replace(Assumptions(), host_clock_scale=lo/(16*125e6),
                        pll_bias_a=pll_current)
            budget=power_budget({'engine':'rf'}, a, {'directions':('rx','tx')},
                                contract, mode=0)
            power_cases.append(dict(lo_hz=lo, static_clock_current_a=bias,
                sum_activity_capacitance_f=cap, assumed_parameters=asdict(a),
                budget=budget, status='assigned_average_current_screen_only'))
    # Store clock trees and FPGA cost once, not in every impairment observation.
    configurations={}
    observations=[]
    for row in rows:
        key=f"{row['recipe']}:{row['clock']}:{row.get('lo_hz', 0):g}:{row.get('clock_policy','default')}"
        config={k:v for k,v in row.items() if k not in
                ('impairment_case','fpga_resampling','quality','resampler_cost')}
        if row.get('resampler_cost') is not None:
            config['optional_fpga_resampler_cost']=row['resampler_cost']
        configurations.setdefault(key,{}).update(config)
        observations.append(dict(configuration_id=key,
            impairment_case=row['impairment_case'],fpga_resampling=row['fpga_resampling'],
            quality=row['quality']))
    lora_study=lora_recovery_suite(contract)
    joined_resources=joined_rf_resource_screen(contract)
    host_coupling=host_charge_pdn_bridge(contract,joined_resources)
    host_harmonics=host_harmonic_screen(host_coupling)
    return dict(milestone='Several credible ways to succeed',
        status='partial_rf_rate_and_joined_spectral_mitigation_screen', complete=False,
        evidence_class='conditional_mathematical_model',
        silicon_measurement_used=False, standards_compliant=False,
        intended_rf_targets=[p['id'] for p in contract['protocol_profiles'] if p['engine']=='rf'],
        still_required_wired_targets=[p['id'] for p in contract['protocol_profiles'] if p['engine']=='wire'],
        impairment_assumptions=CASES,
        acceptance='Diagnostic EVM <= 10%, zero fixture symbol errors, acquisition and no clipped converter samples; not a protocol mask.',
        operating_point='Rate-only comparisons: fixed 3.25 V RF rail, 12 dB backoff and assigned IID phase. Joined spectral subsection replaces IID phase with its declared mixer spectra and common sample timing; neither is measured silicon.',
        configurations=configurations, observations=observations, clock_power_cases=power_cases,
        capability_coverage=capability_coverage(contract,configurations,observations),
        control_surface_coverage=control_surface_coverage(contract),
        weak_rf_recipe_controls=weak_rf_recipe_controls(contract),
        lora_recovery=lora_study,
        rf_bench_diagnostics=rf_bench_diagnostics(lora_study),
        joined_rf_resources=joined_resources,
        rf_dc_quality=rf_dc_quality_bridge(contract,joined_resources),
        host_charge_coupling=host_coupling,
        host_harmonics=host_harmonics,
        shared_timing_requirements=shared_timing_requirements(host_harmonics),
        rf_transition_requirements=rf_transition_requirements(),
        host_driven_wired_receiver=host_driven_wired_receiver(host_coupling),
        host_driven_rf_receiver=host_driven_rf_receiver(contract,host_coupling),
        bidirectional_host_receiver=bidirectional_host_receiver_screen(contract,host_coupling),
        common_feed_rf=common_feed_rf_screen(contract,host_coupling),
        whole_chip_operating_envelopes=whole_chip_operating_envelopes(contract),
        shared_packet_lifecycle=shared_packet_lifecycle(contract),
        tx_clock_spurs=tx_clock_spur_envelope(contract),
        local_decoupling=local_decoupling_envelope(contract),
        analog_wake=analog_wake_envelope(),
        loaded_clock_packet_exchange=loaded_clock_packet_exchange(contract),
        reference_supply=reference_supply_screen(contract,host_coupling),
        rf_host_rate_comparison=rf_host_rate_comparison(contract,host_coupling),
        absolute_rf_input=absolute_rf_screen(contract,host_coupling),
        rf_gain_headroom=rf_gain_headroom_requirements(),
        wideband_filter_requirements=wideband_filter_requirements(),
        wideband_filter_waveform=wideband_filter_waveform(),
        ble_packet_acquisition=ble_packet_campaign(),
        reference_load=reference_load_requirements(),
        spectral_rf_mitigations=spectral_suite(contract),
        host_pdn_mitigations=host_pdn_suite(contract),
        shared_return_mitigations=shared_return_suite(contract),
        explicit_gain_mitigations=explicit_gain_suite(contract),
        diagnostic_observability=diagnostic_observability_suite(contract),
        wired_operating_envelopes=wired_operating_envelopes(contract),
        causal_wired_receiver=causal_receiver_envelope(impaired=True),
        wired_resource_requirements=wired_resource_requirements(contract),
        tx_spectral=tx_spectral_suite(),
        tx_image_attribution=tx_image_attribution_suite(),
        area=dict(contract_allocations_um2=contract['area_um2'],
                  limit_um2=contract['limits']['core_area_um2'],
                  added_clock_routes_and_trims_area_um2=None,
                  fit_verified=False),
        unresolved=['complete spectral clock/RF/blocker/coexistence model beyond the joined diagnostic receive scenario',
            'independent external RF source and complete ADC/DAC clock-edge owner',
            'standards acquisition, packets, EVM masks and full MCS coverage',
            'finite TX pacing, transport recovery and complete storage ledger',
            'FPGA resampler implementation, quantization and latency integration',
            'actual circuit area/current, protected input bandwidth and quadrature',
            'first-silicon observability implementation and fault discrimination'],
        sources_sha256={name:hashlib.sha256((P/name).read_bytes()).hexdigest() for name in (
            'verification/robustness_envelope.py', 'spec/contract.json',
            'rtl/pt_spi.sv','rtl/pt_stream_rx.sv','integration/pt_chip.sv',
            'verification/recovery_mailbox.py',
            'verification/wired_envelope.py','verification/ble_packet.py','verification/check_contract.py',
            'system_model/connected/wired_blocks.py',
            'system_model/connected/tx_output_candidate.py',
            'system_model/connected/tx_output_stage.py',
            'system_model/architecture_fast/behavioral.py',
            'system_model/architecture_fast/resource_configuration.py',
            'system_model/connected/oscillator_noise.py',
            'system_model/connected/protocol_pad.py',
            'system_model/connected/protocol_signals.py')})


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--wideband-filter',action='store_true',help='Fast wideband passband/selectivity architecture requirements')
    modes.add_argument('--analog-wake',action='store_true',help='Fast continuous-state analog load wake/mute disturbance')
    modes.add_argument('--whole-chip',action='store_true',help='Run only the shared-environment RF/wired comparison and print JSON; does not refresh the full evidence report')
    modes.add_argument('--loaded-clock-exchange',action='store_true',help='Paired actual packet exchange with delivered versus loaded clock input')
    modes.add_argument('--local-decoupling',action='store_true',help='Fast shared RF/wired nonideal local-capacitor and timing screen')
    modes.add_argument('--clock-spurs',action='store_true',help='Fast supply-induced TX spur map across carrier and host divider choices')
    modes.add_argument('--packet-lifecycle',action='store_true',help='Run shared-environment packet RX, timed DAC reply and peer observation; print JSON')
    modes.add_argument('--ble-only',action='store_true',help='Refresh packet bench only when every other recorded source hash is unchanged')
    args=parser.parse_args()
    if args.wideband_filter:
        print(json.dumps(dict(requirements=wideband_filter_requirements(),waveform=wideband_filter_waveform()),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.analog_wake:
        print(json.dumps(analog_wake_envelope(),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.loaded_clock_exchange:
        print(json.dumps(loaded_clock_packet_exchange(json.loads((P/'spec/contract.json').read_text())),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.local_decoupling:
        print(json.dumps(local_decoupling_envelope(json.loads((P/'spec/contract.json').read_text())),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.whole_chip:
        print(json.dumps(whole_chip_operating_envelopes(json.loads((P/'spec/contract.json').read_text())),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.clock_spurs:
        print(json.dumps(tx_clock_spur_envelope(json.loads((P/'spec/contract.json').read_text())),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.packet_lifecycle:
        print(json.dumps(shared_packet_lifecycle(json.loads((P/'spec/contract.json').read_text())),indent=2,allow_nan=False))
        raise SystemExit(0)
    if args.ble_only:
        path=P/'evidence/robustness-envelope.json'
        result=json.loads(path.read_text())
        packet_source='verification/ble_packet.py'
        changed=[name for name,digest in result['sources_sha256'].items()
                 if name!=packet_source and hashlib.sha256((P/name).read_bytes()).hexdigest()!=digest]
        if packet_source not in result['sources_sha256'] or changed:
            parser.error('Full report required: missing BLE provenance or changed sources: '+', '.join(changed))
        result['ble_packet_acquisition']=ble_packet_campaign()
        result['shared_packet_lifecycle']=shared_packet_lifecycle(json.loads((P/'spec/contract.json').read_text()))
        result['loaded_clock_packet_exchange']=loaded_clock_packet_exchange(json.loads((P/'spec/contract.json').read_text()))
        result['sources_sha256'][packet_source]=hashlib.sha256((P/packet_source).read_bytes()).hexdigest()
        write_evidence(path,result)
        print('BLE packet section refreshed; other recorded model sources unchanged. Whole-chip milestone incomplete.')
        raise SystemExit(0)
    result=run()
    path=P/'evidence/robustness-envelope.json'
    write_evidence(path,result)
    for impairment in CASES:
        selected=[r for r in result['observations'] if r['impairment_case']==impairment
                  and r['configuration_id'].startswith('wifi_he20__40000000.0:external_lo:')
                  and r['fpga_resampling']]
        print(impairment, 'wideband resampled EVM range',
              [min(r['quality']['evm_rms'] for r in selected),
               max(r['quality']['evm_rms'] for r in selected)])
    print('All desired failures retained. Whole-chip milestone remains incomplete.')
    print('Report:',path)
