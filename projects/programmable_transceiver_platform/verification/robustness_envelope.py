"""Fast mitigation comparison using existing RF waveforms and declared budgets.

Not an end-to-end chip qualification. Every desired failure is retained and
unimplemented clock, bridge, circuit and FPGA requirements remain explicit.
"""
import hashlib
import json
import math
from dataclasses import replace, asdict
from pathlib import Path
import sys

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'system_model/architecture_fast'))
import numpy as np
from behavioral import Assumptions, waveform_screen, power_budget
from protocol_signals import fixture, gfsk, lora
from resource_configuration import validate_rf_settings
from oscillator_noise import PhaseNoise
from wired_envelope import wired_operating_envelopes, causal_receiver_envelope, wired_resource_requirements


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
                       board_c=0., board_esr=.05, board_esl=1e-9):
    """Two-node small-signal PDN, host current at board node, victim at die.

    Board capacitor is outside the package, including ESR/ESL. Positive load
    current gives negative voltage. Returns complex transimpedance and KCL
    residual for a one-ampere test input; no fitted isolation multiplier.
    """
    values=(frequency_hz,feed_r,feed_l,package_r,package_l,die_c,board_c,board_esr,board_esl)
    if not all(math.isfinite(x) and x>=0 for x in values) or min(frequency_hz,feed_r,package_r,die_c)<=0:
        raise ValueError('Finite passive PDN and positive frequency required')
    w=2*math.pi*frequency_hz
    ys=1/(feed_r+1j*w*feed_l);yp=1/(package_r+1j*w*package_l)
    yb=0j if board_c==0 else 1/(board_esr+1j*w*board_esl+1/(1j*w*board_c))
    yd=1j*w*die_c
    matrix=np.array([[ys+yb+yp,-yp],[-yp,yp+yd]],complex)
    solution=np.linalg.solve(matrix,np.array([-1.,0.]))
    return dict(board_ohm=complex(solution[0]),die_ohm=complex(solution[1]),
                kcl_residual_a=float(max(abs(matrix@solution-np.array([-1.,0.])))))


def shared_return_transfer(frequency_hz, *, return_r=.1, return_l=2e-9,
                          shared_fraction=1., **network):
    """Three-node board supply / die supply / die return network.

    On-die decoupling connects die supply to die return; board decoupling goes
    to the ideal board return. The specified fraction of host current returns
    through the victim return impedance. Solve together, not by subtracting an
    independently calculated ground bounce from a fixed supply waveform.
    """
    if (not all(math.isfinite(v) for v in (return_r,return_l,shared_fraction))
            or return_r<0 or return_l<0 or not 0<=shared_fraction<=1):
        raise ValueError('Passive finite return and bounded sharing required')
    # Reuse validation of the supply network and its ideal-return limit.
    baseline=board_die_transfer(frequency_hz,**network)
    if return_r==0 and return_l==0:
        return dict(differential_ohm=baseline['die_ohm'],ground_ohm=0j,
                    board_ohm=baseline['board_ohm'],die_ohm=baseline['die_ohm'],
                    kcl_residual_a=baseline['kcl_residual_a'],power_residual_w=0.)
    n=dict(feed_r=2.,feed_l=2e-9,package_r=.1,package_l=2e-9,
           die_c=100e-12,board_c=0.,board_esr=.05,board_esl=1e-9)
    n.update(network);w=2*math.pi*frequency_hz
    ys=1/(n['feed_r']+1j*w*n['feed_l'])
    yp=1/(n['package_r']+1j*w*n['package_l'])
    yg=1/(return_r+1j*w*return_l);yd=1j*w*n['die_c']
    yb=0j if n['board_c']==0 else 1/(n['board_esr']+1j*w*n['board_esl']+1/(1j*w*n['board_c']))
    matrix=np.array([[ys+yb+yp,-yp,0],[-yp,yp+yd,-yd],[0,-yd,yg+yd]],complex)
    injection=np.array([-1.,0.,shared_fraction])
    vb,vd,vg=np.linalg.solve(matrix,injection)
    supplied=float(np.real(np.vdot(injection,[vb,vd,vg]))/2)
    loss=(abs(vb)**2*(ys.real+yb.real)+abs(vb-vd)**2*yp.real+abs(vg)**2*yg.real)/2
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


def host_harmonic_screen(coupling):
    word=2.437e9/8;rows=[]
    for candidate in coupling['cases']:
        if candidate['name'] not in ('existing_10uf','lower_feed_resistance','lower_feed_adverse_cap'):continue
        for tau in (.25e-9,.5e-9,1e-9):
            tones=[]
            for harmonic in range(1,7):
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
    return dict(cases=rows,status='periodic_mean_current_harmonics_not_full_noise_spectrum',
        scope=['Same random-data mean activity, 10 pF load, 7 pC internal charge and network hypotheses as the DC/activity screen.',
            'Capacitive current uses a 10 mA rectangular charge pulse; internal charge uses an exponential pulse with assigned 0.25/0.5/1 ns decay.',
            'Pulse origins are aligned. Coherent bank summation models a possible synchronous mean-current component, not an independently verified worst case.',
            'Six forwarded-clock harmonics through 913.875 MHz are resolved; random-data continuous spectrum, jitter and higher harmonics are omitted.',
            'Do not extrapolate the 1 MHz residual oscillator-pushing number to these frequencies. Frequency-dependent supply-to-delay/phase transfer remains unknown.',
            'No RF EVM verdict: carrier sidebands, ADC aliasing and shared-clock phase correlations require a frequency-resolved clock model.',
            'Pulse-charge accounting does not establish valid GPIO settling, receiver sampling or real device current waveforms.'])


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
    for profile in contract['protocol_profiles']:
        rf=profile['engine']=='rf'
        capabilities.append(dict(target=profile['id'],
            quantitative_evidence=('RF rate/precision fixture sweep' if rf else 'generic NRZ electrical/timing sweep'),
            joined_evidence=('HE20-only loaded spectral TX and blocked RX comparisons' if profile['id']=='wifi_he20' else
                '2.5 Gb/s random-NRZ causal receiver' if profile['id']=='pcie_gen1' else None),
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
        weak_rf_recipe_controls=weak_rf_recipe_controls(contract),
        lora_recovery=lora_study,
        rf_bench_diagnostics=rf_bench_diagnostics(lora_study),
        joined_rf_resources=joined_resources,
        rf_dc_quality=rf_dc_quality_bridge(contract,joined_resources),
        host_charge_coupling=host_coupling,
        host_harmonics=host_harmonic_screen(host_coupling),
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
            'verification/wired_envelope.py',
            'system_model/connected/wired_blocks.py',
            'system_model/connected/tx_output_candidate.py',
            'system_model/connected/tx_output_stage.py',
            'system_model/architecture_fast/behavioral.py',
            'system_model/architecture_fast/resource_configuration.py',
            'system_model/connected/oscillator_noise.py',
            'system_model/connected/protocol_signals.py')})


if __name__ == '__main__':
    result=run()
    path=P/'evidence/robustness-envelope.json'
    path.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    for impairment in CASES:
        selected=[r for r in result['observations'] if r['impairment_case']==impairment
                  and r['configuration_id'].startswith('wifi_he20__40000000.0:external_lo:')
                  and r['fpga_resampling']]
        print(impairment, 'wideband resampled EVM range',
              [min(r['quality']['evm_rms'] for r in selected),
               max(r['quality']['evm_rms'] for r in selected)])
    print('All desired failures retained. Whole-chip milestone remains incomplete.')
    print('Report:',path)
