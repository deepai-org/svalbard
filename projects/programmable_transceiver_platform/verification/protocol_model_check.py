"""Executable PHY primitives and canonical coupling, not protocol certification.

One report covers all intended new profiles. Independent symbol observers,
negative controls, exact RC comparisons, source hashes and explicit gaps prevent
primitive passes from being interpreted as complete packet/system qualification.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from full_chip_model import make_chip, parameters
from fast_loaded_output import P
from protocol_signals import fixture, decisions, Waveform, he20, TrainedBlockEqualizer, repeated_training_frequency, lora
from protocol_pad import SharedWiredPad, usb_nrzi, usb_decode, sata_oob, detect_oob, response_budget, usb_framed_turnaround
from pll_serializer import PLLSerializer


def reject(fn,kind=ValueError):
    try:fn()
    except kind:return
    raise AssertionError('Invalid operation accepted')


def waveform_checks():
    rows=[]
    for profile,variants in [('wifi_he20',['']),('bluetooth_le',['1m','2m','s2','s8']),
            ('bluetooth_br_edr',['br','edr2','edr3']),('ieee802154_24',['']),('lora_24',[''])]:
        c=make_chip(protocol=profile);service=c.protocol_service
        for variant in variants:
            w=service.waveform(variant);observed=decisions(w)
            assert np.array_equal(observed,w.symbols),(profile,variant)
            corrupt=w.samples.conj() if w.kind in ('gfsk','edr') else -w.samples
            if w.kind=='lora':corrupt=w.samples*np.exp(2j*math.pi*np.arange(len(w.samples))/(1<<w.metadata['sf']))
            assert np.count_nonzero(decisions(w,corrupt)!=w.symbols)>0
            out,clipped=service.project_receive(w)
            assert len(out)==len(w.samples) and np.all(np.isfinite(out)) and clipped==0
            tx=service.project_transmit(w)
            assert tx.shape==w.samples.shape and np.all(np.isfinite(tx)) and np.max(abs(tx))>0
            assert c.time==0 and c.analog_owner.time==0,'Reduced projection must not advance canonical state'
            changed,_=service.project_receive(w,phase_rad=np.linspace(0,.7,len(w.samples)))
            assert np.max(abs(out-changed))>1e-4,'Projection ignored LO impairment'
            rows.append(dict(profile=profile,variant=variant or 'default',samples=len(w.samples),
                observed_symbol_errors=0,negative_control_detected=True,
                projected_rms=float(np.sqrt(np.mean(abs(out)**2))),projected_clipping=clipped,
                projected_tx_rms=float(np.sqrt(np.mean(abs(tx)**2))),
                scope='PHY symbol fixture and frozen-rail canonical-filter reduction; no packet/PER claim'))
        # Context lifetime follows selected profile, never manufactures a ready/lock flag.
        center=(service.selected['carrier_min_hz']+service.selected['carrier_max_hz'])/2
        service.save_context(0,center)
        service.select(profile)
        reject(lambda:service.request_hop(0))
    return rows


def link_quality_checks():
    """Measure actual cascade decisions, including failures; no fitted correction."""
    rows=[]
    profiles=[('wifi_he20',['']),('bluetooth_le',['1m','2m','s2','s8']),
              ('bluetooth_br_edr',['br','edr2','edr3']),
              ('ieee802154_24',['']),('lora_24',[''])]
    for profile,variants in profiles:
        c=make_chip(protocol=profile);service=c.protocol_service
        for variant in variants:
            for seed in (81,82,83):
                w=service.waveform(variant,seed)
                for bits in (8,12):
                    z,clipped=service.project_link(w,bits=bits)
                    observed=decisions(w,z)
                    assert observed.shape==w.symbols.shape and clipped==0
                    errors=int(np.count_nonzero(observed!=w.symbols))
                    # Quality is measured separately from harness correctness.
                    # Do not turn an observed design gap into a claimed pass.
                    lost,_=service.project_link(w,bits=bits,channel_gain=0.)
                    assert np.count_nonzero(decisions(w,lost)!=w.symbols)>0
                    noisy,_=service.project_link(w,bits=bits,noise_rms=.3,seed=seed)
                    assert np.max(abs(noisy-z))>.01
                    offset,_=service.project_link(w,bits=bits,frequency_offset_hz=100e3)
                    assert np.max(abs(offset-z))>.01
                    assert c.time==0 and c.analog_owner.time==0
                    rows.append(dict(profile=profile,variant=variant or 'default',seed=seed,
                        converter_bits=bits,symbols=len(w.symbols),symbol_errors=errors,
                        symbol_error_ratio=errors/len(w.symbols),adc_clipped_samples=clipped,
                        quality_status='open' if errors else 'finite_fixture_pass',
                        noise_symbol_errors=int(np.count_nonzero(decisions(w,noisy)!=w.symbols)),
                        offset_symbol_errors=int(np.count_nonzero(decisions(w,offset)!=w.symbols)),
                        scope='frozen-rail pre-pad TX/channel/RX cascade; known symbol timing, no equalization or packet claim'))
        reject(lambda:service.project_link(w,noise_rms=-1))
    return rows


def rf_conversion_impairment_checks():
    """Configured frontend and separate LO histories survive the fast chain."""
    from receiver_impairments import Frontend
    rows=[]
    for name in ('wifi_he20','bluetooth_le','bluetooth_br_edr','ieee802154_24','lora_24'):
        chip=make_chip(protocol=name);service=chip.protocol_service;wave=service.waveform()
        clean,_=service.project_link(wave,bits=12)
        chip.frontend=Frontend(gain_error=.02,phase_error=.03,saturation=.3,noise_rms=.0003,seed=7531)
        before=chip.frontend.rng.getstate()
        impaired,clipped=service.project_link(wave,bits=12)
        repeat,_=service.project_link(wave,bits=12)
        assert np.array_equal(impaired,repeat)
        assert chip.frontend.count==0 and chip.frontend.rng.getstate()==before
        assert np.max(abs(impaired-clean))>1/2048
        phase=.04*np.sin(2*math.pi*1e6*np.arange(len(wave.samples))/wave.sample_hz)
        common,_=service.project_link(wave,bits=12,tx_phase_rad=phase,rx_phase_rad=phase)
        independent,_=service.project_link(wave,bits=12,tx_phase_rad=phase,rx_phase_rad=-phase)
        assert np.max(abs(common-impaired))<1e-12
        assert np.max(abs(independent-impaired))>1/2048
        rows.append(dict(profile=name,adc_clipped_samples=clipped,
            impaired_symbol_errors=int(np.count_nonzero(decisions(wave,impaired)!=wave.symbols)),
            independent_phase_symbol_errors=int(np.count_nonzero(decisions(wave,independent)!=wave.symbols)),
            frontend_change_rms=float(np.sqrt(np.mean(abs(impaired-clean)**2))),
            phase_change_rms=float(np.sqrt(np.mean(abs(independent-impaired)**2)))))
        assert chip.time==chip.analog_owner.time==0.
    return dict(cases=rows,physical_qualification=False,
        assumptions='Frontend ±2% gain, .03 rad quadrature error, .3 V soft compression, .3 mV per-quadrature sampled noise; prescribed .04 rad LO sine, not device data',
        scope='Frozen-rail TX/channel/RX projection, configured frontend before ADC; clocks/host not acquired')


def clocked_rf_conversion_checks():
    service=make_chip(protocol='wifi_he20').protocol_service
    network=service.chip.output_network
    network.configure(True,False)
    before=network.voltage.copy();time_before=network.time
    source=np.array([.1+.02j,-.08+.01j,.03-.04j])
    projected=network.project_samples(source,40e6)
    reference_network=copy.deepcopy(network);reference=[]
    for value in source:
        reference_network.advance(reference_network.time+1/40e6,value)
        reference.append(reference_network.voltage[1])
    assert np.max(abs(projected-reference))<1e-12
    assert np.array_equal(network.voltage,before) and network.time==time_before
    network.configure(False,True)
    isolated=network.project_samples(source,40e6)
    assert np.linalg.norm(isolated)<.01*np.linalg.norm(projected)
    network.configure(True,False)
    training=np.random.default_rng(900).integers(0,2,468)
    payload=np.random.default_rng(81).integers(0,2,2340)
    waveform=he20(np.r_[training,payload]);bins=np.asarray(waveform.metadata['data'])%256
    rows=[]
    for bits in (8,12):
        previous=None;differences=[]
        for substeps in (2,4,8):
            result=service.project_clocked_link(waveform,bits=bits,substeps=substeps)
            ratio=2 if bits==12 else 1
            assert result['adc_samples']==result['dac_updates']==len(waveform.samples)*ratio
            assert abs(result['times'][-1]-waveform.duration)<1e-15
            # Explicit external decimation for the existing fixed-grid observer.
            z=result['samples'][ratio-1::ratio]
            if previous is not None:differences.append(float(np.sqrt(np.mean(abs(z-previous)**2))))
            previous=z
            eq=TrainedBlockEqualizer(256,16,bins)
            rejected=None;errors=evm=None
            try:eq.train(waveform.samples[:544],z[:544])
            except ValueError as error:
                rejected=str(error);reject(lambda:eq.observe(z[544:]))
            else:
                observed=eq.observe(z[544:]);reference=eq.spectrum(waveform.samples[544:])
                errors=int(np.count_nonzero((observed.real>0).ravel()!=payload))
                evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
            rows.append(dict(bits=bits,converter_hz=result['converter_hz'],substeps=substeps,
                training_rejected=rejected,tx_pad_included=True,
                adc_samples=result['adc_samples'],symbol_errors=errors,evm_rms=evm,
                adc_clipped_samples=result['adc_clipped_samples']))
        assert differences[1]<differences[0],differences
    from receiver_impairments import Frontend
    combined=[]
    phase=lambda t:.04*np.sin(2*math.pi*1e6*t)
    reject(lambda:service.project_clocked_link(waveform,tx_phase=np.zeros(3)))
    for bits in (8,12):
        for gain in (.5,1.,2.):
            service.chip.configure_rx_gain(gain)
            service.chip.frontend=Frontend(gain_error=.02,phase_error=.03,
                saturation=.3,noise_rms=.0003,seed=7531)
            initial_rng=service.chip.frontend.rng.getstate()
            result=service.project_clocked_link(waveform,bits=bits,substeps=8,
                tx_phase=phase,rx_phase=lambda t:-phase(t))
            assert service.chip.frontend.count==0 and service.chip.frontend.rng.getstate()==initial_rng
            ratio=2 if bits==12 else 1
            z=result['samples'][ratio-1::ratio]
            eq=TrainedBlockEqualizer(256,16,bins)
            rejected=None;errors=evm=None
            try:eq.train(waveform.samples[:544],z[:544])
            except ValueError as error:rejected=str(error)
            else:
                observed=eq.observe(z[544:]);reference=eq.spectrum(waveform.samples[544:])
                errors=int(np.count_nonzero((observed.real>0).ravel()!=payload))
                evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
            combined.append(dict(bits=bits,rx_gain=gain,training_rejected=rejected,
                symbol_errors=errors,evm_rms=evm,adc_clipped_samples=result['adc_clipped_samples']))
    isolation=[]
    service.chip.configure_rx_gain(1.)
    conditions=(('nominal',{},False),('iq',dict(gain_error=.02,phase_error=.03),False),
        ('compression',dict(saturation=.3),False),('noise',dict(noise_rms=.0003),False),
        ('lo',{},True),('combined',dict(gain_error=.02,phase_error=.03,saturation=.3,noise_rms=.0003),True))
    for seed in (81,82):
        labels=np.random.default_rng(seed).integers(0,2,2340)
        stimulus=he20(np.r_[training,labels])
        for name,parameters,with_lo in conditions:
            service.chip.frontend=Frontend(**parameters,seed=7531+seed)
            result=service.project_clocked_link(stimulus,bits=12,substeps=8,
                tx_phase=phase if with_lo else None,
                rx_phase=(lambda t:-phase(t)) if with_lo else None)
            z=result['samples'][1::2]
            eq=TrainedBlockEqualizer(256,16,bins)
            rejected=None;errors=evm=None
            try:eq.train(stimulus.samples[:544],z[:544])
            except ValueError as error:rejected=str(error)
            else:
                observed=eq.observe(z[544:]);reference=eq.spectrum(stimulus.samples[544:])
                errors=int(np.count_nonzero((observed.real>0).ravel()!=labels))
                evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
            isolation.append(dict(condition=name,payload_seed=seed,training_rejected=rejected,
                symbol_errors=errors,evm_rms=evm,adc_clipped_samples=result['adc_clipped_samples']))
    assert service.chip.time==0.
    return dict(cases=rows,combined_frontend_lo=combined,loaded_chain_isolation=isolation,quality_closed=False,
        scope='Actual converter-rate ZOH source sampling and quantization; refined left-held TX-to-RX forcing; frozen rails, nominal and combined frontend/LO cases, two held-out synthetic HE20 BPSK payloads for unity-gain impairment isolation',
        limitations=['Substep convergence is a screen, not a continuous-time error bound.',
            'No acquired clocks/host traffic, packet preamble, timing recovery or compliance.'])


def rf_startup_solver_checks():
    from driver_pll_feedback import forecast_trajectory_feedback
    chip=make_chip(protocol='wifi_he20');chip.configure_analog_loads()
    owner=chip.analog_owner
    from scipy.linalg import expm
    network=copy.deepcopy(owner.network)
    network.voltage=np.array([.001+.002j,-.001j,.0003,0j])
    exact_cases=[]
    # Independent augmented-state matrix exponential, including a repeated pole.
    for rate in (0j,2j*math.pi*108e6,complex(np.linalg.eigvals(network.A)[0])):
        initial=network.voltage.copy();dt=.5/abs(rate.real) if rate.real<0 else 10e-9
        amplitude=.0025+.001j
        matrix=np.zeros((5,5),complex);matrix[:4,:4]=network.A
        matrix[:4,4]=np.linalg.solve(network.C,np.array([amplitude/50,0,0,0]))
        matrix[4,4]=rate
        expected=(expm(matrix*dt)@np.r_[initial,1.])[:4]
        projected=network.forecast_terms(dt,[(amplitude,rate)])
        error=float(np.max(abs(projected-expected)))
        assert error<1e-12 and np.array_equal(network.voltage,initial)
        exact_cases.append(dict(interval_s=dt,rate_real=rate.real,rate_imag=rate.imag,error_v=error))
    # Real zero-code TX still has LO feedthrough: do not claim the quiet path
    # applies to normal coarse startup. Compare stiff solvers on that source.
    from tx_output_terms import output_terms
    import time
    leakage=output_terms(chip.tx.transmit_terms(),**chip.tx_output_parameters)
    assert any(a!=0 for a,_ in leakage)
    reject(lambda:forecast_trajectory_feedback(owner,chip.rf_pll,10e-9,leakage,
        chip.rf_hz_per_v,.5e-9,receive_transform=lambda t,v,p:0j,quiet_rf=True))
    candidates=[];elapsed=[]
    for method in ('Radau','BDF'):
        start=time.monotonic()
        candidates.append(forecast_trajectory_feedback(owner,chip.rf_pll,10e-9,leakage,
            chip.rf_hz_per_v,.5e-9,receive_transform=lambda t,v,p:0j,solver_method=method))
        elapsed.append(time.monotonic()-start)
    stiff_rail=float(np.max(abs(candidates[0][0].domains.voltage-candidates[1][0].domains.voltage)))
    stiff_pad=float(np.max(abs(candidates[0][0].network.voltage-candidates[1][0].network.voltage)))
    stiff_phase=abs(candidates[0][1].output_phase_cycles-candidates[1][1].output_phase_cycles)
    assert stiff_rail<1e-8 and stiff_pad<1e-8 and stiff_phase<1e-8
    retained,retained_clock,_=candidates[0]
    assert np.linalg.norm(retained.network.voltage)>0
    retained.network.configure(True,False)
    dynamic=[];dynamic_elapsed=[]
    for method in ('Radau','BDF'):
        start=time.monotonic()
        dynamic.append(forecast_trajectory_feedback(retained,retained_clock,
            retained.time+2e-9,[(.02+.01j,2j*math.pi*10e6)],chip.rf_hz_per_v,.5e-9,
            receive_transform=lambda t,v,p:v*np.exp(-1j*p),solver_method=method))
        dynamic_elapsed.append(time.monotonic()-start)
    differences=dict(
        rail_v=float(np.max(abs(dynamic[0][0].domains.voltage-dynamic[1][0].domains.voltage))),
        pad_v=float(np.max(abs(dynamic[0][0].network.voltage-dynamic[1][0].network.voltage))),
        rx_v=float(np.max(abs(np.asarray(dynamic[0][0].rx_bank['states'])-np.asarray(dynamic[1][0].rx_bank['states'])))),
        phase_cycles=abs(dynamic[0][1].output_phase_cycles-dynamic[1][1].output_phase_cycles))
    assert all(v<1e-8 for v in differences.values()),differences
    assert np.linalg.norm(dynamic[0][0].rx_bank['states'])>0
    assert retained.time==10e-9 and owner.time==chip.rf_pll.time==0.
    # Retain the rail/detector/RX/energy equations while eliminating only the
    # passive network's stiff state integration. Source swing is held per segment.
    amplitude=.0025;rate=2j*math.pi*108e6;end=10e-9
    command=lambda t:amplitude*np.exp(rate*t)
    reference_driver=copy.deepcopy(owner)
    reference_driver.advance(end,command,solver_method='BDF',rtol=1e-10,atol=1e-13,rail_trace_step_s=25e-12)
    reduced_cases=[]
    for segments in (1,2,4):
        reduced=copy.deepcopy(owner);start=time.monotonic();source_error=0.
        for segment in range(segments):
            terms=[(reduced.law.source(command(reduced.time),reduced.rail_v),rate)]
            reduced.advance((segment+1)*end/segments,command,solver_method='BDF',
                rtol=1e-10,atol=1e-13,passive_terms=terms,source_error_limit_v=1e-4)
            source_error=max(source_error,reduced.passive_source_error_v)
        reduced_cases.append(dict(segments=segments,elapsed_s=time.monotonic()-start,
            source_error_at_solver_evaluations_v=source_error,
            rail_error_v=float(np.max(abs(reduced.domains.voltage-reference_driver.domains.voltage))),
            pad_error_v=float(np.max(abs(reduced.network.voltage-reference_driver.network.voltage))),
            source_energy_error_j=abs(reduced.domains.source_energy_j-reference_driver.domains.source_energy_j)))
    assert reduced_cases[-1]['pad_error_v']<reduced_cases[0]['pad_error_v']
    failed=copy.deepcopy(owner);before=failed.network.voltage.copy();rails=failed.domains.voltage.copy()
    reject(lambda:failed.advance(end,command,solver_method='BDF',passive_terms=[(amplitude,rate)],
        source_error_limit_v=1e-9))
    assert failed.time==0 and np.array_equal(failed.network.voltage,before) and np.array_equal(failed.domains.voltage,rails)
    adaptive,adaptation=owner.forecast_passive(end,[(amplitude,rate)],source_error_limit_v=3e-6,record_states=True)
    assert all(row['source_error_v']<=3e-6 for row in adaptation['segments'])
    assert adaptation['attempts']>len(adaptation['segments'])>1
    assert adaptive.rail_trajectory.times[0]==owner.time and adaptive.rail_trajectory.times[-1]==end
    assert all(b>a for a,b in zip(adaptive.rail_trajectory.times,adaptive.rail_trajectory.times[1:]))
    adaptive_pad=float(np.max(abs(adaptive.network.voltage-reference_driver.network.voltage)))
    adaptive_energy=abs(adaptive.domains.source_energy_j-reference_driver.domains.source_energy_j)
    assert adaptive_energy<reduced_cases[-1]['source_energy_error_j']
    reject(lambda:owner.forecast_passive(end,[(amplitude,rate)],source_error_limit_v=3e-6,
        maximum_attempts=1))
    assert owner.time==0 and np.array_equal(owner.network.voltage,before) and np.array_equal(owner.domains.voltage,rails)
    transient_reference=copy.deepcopy(owner);pad_errors=[];rail_errors=[]
    for row in adaptation['segments']:
        for checkpoint,voltage in row['pad_observations']:
            transient_reference.advance(checkpoint,command,solver_method='BDF',rtol=1e-10,atol=1e-13)
            pad_errors.append(float(np.max(abs(voltage-transient_reference.network.voltage))))
        rail_errors.append(float(np.max(abs(row['end_rails']-transient_reference.domains.voltage))))
    assert max(pad_errors)<3e-6 and max(rail_errors)<1e-8
    assert np.max(abs(transient_reference.network.voltage-reference_driver.network.voltage))<1e-10
    projected_clocks=[]
    for driver in (reference_driver,adaptive):
        clock=copy.copy(chip.rf_pll)
        clock.set_supply_trajectory(driver.domain_trajectories['PLL'],chip.rf_hz_per_v)
        clock.advance(end);projected_clocks.append(clock)
    rail_driven_phase_error=abs(projected_clocks[0].output_phase_cycles-projected_clocks[1].output_phase_cycles)
    assert rail_driven_phase_error<1e-5
    adaptive_report=dict(attempts=adaptation['attempts'],segments=len(adaptation['segments']),
        peak_sampled_source_error_v=max(r['source_error_v'] for r in adaptation['segments']),
        pad_error_v=adaptive_pad,source_energy_error_j=adaptive_energy,
        intermediate_pad_error_v=max(pad_errors),intermediate_rail_error_v=max(rail_errors),
        checked_transient_points=len(pad_errors),rail_driven_pll_phase_error_cycles=rail_driven_phase_error,
        merged_rail_history=True,exhausted_budget_preserves_caller=True,
        continuous_error_bound=False)
    return dict(adaptive_passive=adaptive_report,passive_reduction=reduced_cases,source_budget_failure_transactional=True,exact_passive_network=exact_cases,interval_s=10e-9,methods=['Radau','BDF'],elapsed_s=elapsed,
        rail_difference_v=stiff_rail,pad_difference_v=stiff_pad,
        phase_difference_cycles=stiff_phase,lo_leakage_prevents_quiet_path=True,
        retained_signal_case=dict(interval_s=2e-9,elapsed_s=dynamic_elapsed,
            differences=differences,rx_loopback_active=True,output_switch_changed=True),
        default_changed=False)


def acquired_rf_projection_checks():
    from oscillator_noise import FrequencyNoise
    from receiver_impairments import Frontend
    service=make_chip(protocol='wifi_he20').protocol_service
    from driver_pll_feedback import forecast_trajectory_feedback
    chip=service.chip;chip.configure_analog_loads();owner=chip.analog_owner
    def forecast(quiet):
        return forecast_trajectory_feedback(owner,chip.rf_pll,1e-9,[(0j,0j)],
            chip.rf_hz_per_v,.5e-9,receive_transform=lambda t,v,p:0j,quiet_rf=quiet)
    explicit,clock,_=forecast(True);implicit,reference,_=forecast(False)
    rail_error=float(np.max(abs(explicit.domains.voltage-implicit.domains.voltage)))
    phase_error=abs(clock.output_phase_cycles-reference.output_phase_cycles)
    assert rail_error<1e-8 and phase_error<1e-8 and explicit.driver_enabled
    owner.network.voltage[0]=1e-30
    reject(lambda:forecast(True))
    owner.network.voltage[0]=0j
    service.chip.output_network.configure(True,False)
    training=np.random.default_rng(900).integers(0,2,468)
    payload=np.random.default_rng(81).integers(0,2,468)
    wave=he20(np.r_[training,payload])
    def phase_function(h):
        def phase(t):
            if np.any(t<h['times'][0]) or np.any(t>h['times'][-1]):
                raise ValueError('Phase requested outside projected history')
            return np.interp(t,h['times'],h['phase_rad'])
        return phase
    def observe(histories):
        result=service.project_clocked_link(wave,bits=12,substeps=8,
            tx_phase=phase_function(histories[0]),rx_phase=phase_function(histories[1]))
        z=result['samples'][1::2]
        eq=TrainedBlockEqualizer(256,16,np.asarray(wave.metadata['data'])%256)
        rejected=None;errors=evm=None
        try:eq.train(wave.samples[:544],z[:544])
        except ValueError as error:rejected=str(error)
        else:
            observed=eq.observe(z[544:]);reference=eq.spectrum(wave.samples[544:])
            errors=int(np.count_nonzero((observed.real>0).ravel()!=payload))
            evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
        return dict(symbol_errors=errors,evm_rms=evm,training_rejected=rejected,
            adc_clipped_samples=result['adc_clipped_samples']),z
    histories_by_rate=[];cases=[];samples=[]
    for cadence in (40e6,80e6):
        histories=[service.project_lo_history(wave.duration,sample_hz=cadence,
            noise=FrequencyNoise.seeded(20000.,seed=seed)) for seed in (7531,7532)]
        assert all(h['acquired'] for h in histories)
        result,z=observe(histories)
        cases.append(dict(phase_sample_hz=cadence,frontend='nominal',**result))
        histories_by_rate.append(histories);samples.append(z)
    phase_errors=[]
    for coarse,fine in zip(*histories_by_rate):
        phase_errors.append(dict(
            shared_knots_max_rad=float(np.max(abs(coarse['phase_rad']-fine['phase_rad'][::2]))),
            interpolation_max_rad=float(np.max(abs(phase_function(coarse)(fine['times'])-fine['phase_rad'])))))
    service.chip.frontend=Frontend(gain_error=.02,phase_error=.03,saturation=.3,
        noise_rms=.0003,seed=7531)
    before=service.chip.frontend.rng.getstate()
    combined,_=observe(histories_by_rate[-1])
    assert service.chip.frontend.count==0 and service.chip.frontend.rng.getstate()==before
    assert service.chip.time==service.chip.rf_pll.time==0.
    reject(lambda:phase_function(histories_by_rate[0][0])(np.array([-1.])))
    return dict(quiet_startup_solver=dict(rail_error_v=rail_error,phase_error_cycles=phase_error,
            retained_state_rejected=True,powered_bias_preserved=True),
        cases=cases,combined_frontend=dict(phase_sample_hz=80e6,**combined),
        phase_refinement=phase_errors,
        adc_refinement_rms_v=float(np.sqrt(np.mean(abs(samples[1]-samples[0])**2))),
        acquired=True,acquisition_s=histories_by_rate[0][0]['acquisition_s'],
        quality_closed=False,scope='Two independently seeded copies of canonical RF oscillator, frozen rails, explicit reference; loaded converter chain and frontend. Coarse startup/host/chip readiness not exercised.',
        remaining='Longer payloads, sustained lock, real oscillator noise and supply feedback; two grids give sensitivity, not a continuous-time error bound')


def chirp_frequency_checks():
    """Longer generic chirp bursts expose residual-CFO sensitivity, not packets."""
    rows=[]
    c=make_chip(protocol='lora_24');service=c.protocol_service
    for sf in (7,10):
        rng=np.random.default_rng(902+sf)
        w=lora(rng.integers(0,1<<sf,64),sf=sf)
        bin_hz=w.sample_hz/(1<<sf)
        for offset_bins in (0.,-.4,.4,-.6,.6):
            z,clipped=service.project_link(w,bits=12,frequency_offset_hz=offset_bins*bin_hz)
            errors=int(np.count_nonzero(decisions(w,z)!=w.symbols))
            assert clipped==0
            if offset_bins==0:assert errors==0
            if abs(offset_bins)>.5:assert errors>0
            rows.append(dict(sf=sf,symbols=64,duration_s=len(w.samples)/w.sample_hz,
                offset_hz=offset_bins*bin_hz,offset_bins=offset_bins,symbol_errors=errors,
                scope='Frozen-rail complete reduced TX/channel/RX chain; known timing, no CFO acquisition, packet coding or physical clock drift.'))
    assert c.time==0 and c.analog_owner.time==0
    return rows


def chirp_training_checks():
    """Known training dechirp plus reused fine-CFO estimator; external FPGA work."""
    rows=[];service=make_chip(protocol='lora_24').protocol_service
    for sf in (7,10):
        n=1<<sf;payload=np.random.default_rng(902+sf).integers(0,n,64)
        w=lora(np.r_[0,0,payload],sf=sf);reference=lora([0],sf=sf).samples
        for offset_bins in (-2.5,-1.5,-.6,.6,1.5,2.5):
            offset=offset_bins*w.sample_hz/n
            z,clipped=service.project_link(w,bits=12,frequency_offset_hz=offset)
            # First chirp absorbs startup. Only received second training chirp
            # and known training shape enter estimation; no payload or CFO oracle.
            training=z[n:2*n]*reference.conj();lag=n//4
            estimated,coherence=repeated_training_frequency(training[:2*lag],lag,w.sample_hz)
            corrected=z*np.exp(-2j*math.pi*estimated*np.arange(len(z))/w.sample_hz)
            errors=int(np.count_nonzero(decisions(w,corrected)[2:]!=payload))
            raw_errors=int(np.count_nonzero(decisions(w,z)[2:]!=payload))
            unambiguous=abs(offset_bins)<2
            assert clipped==0 and raw_errors>0
            assert (errors==0) if unambiguous else (errors>0)
            rows.append(dict(sf=sf,offset_hz=offset,estimate_error_hz=estimated-offset,
                coherence=coherence,symbols=64,symbol_errors=errors,uncorrected_errors=raw_errors,
                within_unambiguous_range=unambiguous,
                scope='Known aligned synthetic training; frozen-rail TX/channel/RX; no packet detector, coarse search, sample drift or clock-noise qualification.'))
    return rows


def track_chirp_blocks(samples,sf,sample_hz,initial_hz):
    """External decision-directed observer; received blocks only, no payload labels."""
    n=1<<sf;reference=lora([0],sf=sf,bandwidth=sample_hz).samples
    estimate=float(initial_hz);symbols=[];estimates=[];t=np.arange(n)/sample_hz
    for block in np.asarray(samples).reshape(-1,n):
        dechirped=block*reference.conj()*np.exp(-2j*math.pi*estimate*t)
        symbol=int(np.argmax(abs(np.fft.fft(dechirped))))
        residual=dechirped*np.exp(-2j*math.pi*symbol*np.arange(n)/n)
        # Decision-directed update can slip an integer bin; tests retain that risk.
        correction=float(np.angle(np.vdot(residual[:-1],residual[1:]))*sample_hz/(2*math.pi))
        estimate+=.5*correction
        symbols.append(symbol);estimates.append(estimate)
    return np.asarray(symbols),estimates


def validate_chirp_training(samples,reference,sample_hz,frequency_hz):
    """Independent known-training admission check, external to the chip."""
    z=np.asarray(samples);ref=np.asarray(reference)
    if z.shape!=ref.shape or z.ndim!=1 or not len(z) or not np.all(np.isfinite(z)):
        raise ValueError('Invalid validation samples')
    corrected=z*np.exp(-2j*math.pi*frequency_hz*np.arange(len(z))/sample_hz)
    power=float(np.vdot(corrected,corrected).real*np.vdot(ref,ref).real)
    if power<1e-20:raise ValueError('Missing validation energy')
    score=float(abs(np.vdot(ref,corrected))/math.sqrt(power))
    if score<.8:raise ValueError('Known training does not validate acquisition')
    return score


def chirp_drift_checks():
    """A training-only estimate cannot track subsequent channel frequency drift."""
    service=make_chip(protocol='lora_24').protocol_service
    sf=10;n=1<<sf;payload=np.random.default_rng(912).integers(0,n,64)
    w=lora(np.r_[0,0,0,payload],sf=sf);reference=lora([0],sf=sf).samples
    tx=service.project_transmit(w,bits=12,amplitude=.1)
    t=np.arange(len(tx))/w.sample_hz;duration=len(tx)/w.sample_hz;bin_hz=w.sample_hz/n
    rows=[]
    for drift_bins in (0.,.4,1.,-1.):
        slope=drift_bins*bin_hz/duration
        incoming=Waveform(tx*np.exp(1j*math.pi*slope*t*t),w.sample_hz,w.kind,w.symbols,w.metadata)
        z,clipped=service.project_receive(incoming,bits=12,amplitude=1.)
        training=z[n:2*n]*reference.conj();lag=n//4
        estimated,coherence=repeated_training_frequency(training[:2*lag],lag,w.sample_hz)
        corrected=z*np.exp(-2j*math.pi*estimated*t)
        decisions_out=decisions(w,corrected)[3:];bad=np.flatnonzero(decisions_out!=payload)
        assert clipped==0
        if drift_bins==0:assert len(bad)==0
        if abs(drift_bins)==1:assert len(bad)>0
        validation=z[2*n:3*n]
        validation_score=validate_chirp_training(validation,reference,w.sample_hz,estimated)
        reject(lambda:validate_chirp_training(validation,reference,w.sample_hz,estimated+bin_hz))
        reject(lambda:validate_chirp_training(np.zeros(n,complex),reference,w.sample_hz,estimated))
        tracked,estimates=track_chirp_blocks(z[3*n:],sf,w.sample_hz,estimated)
        tracked_errors=int(np.count_nonzero(tracked!=payload))
        assert tracked_errors==0,(drift_bins,tracked_errors)
        wrong,_=track_chirp_blocks(z[3*n:],sf,w.sample_hz,estimated+bin_hz)
        wrong_errors=int(np.count_nonzero(wrong!=payload))
        assert wrong_errors>0,'Decision-directed tracker concealed integer-bin ambiguity'

        rows.append(dict(validation_score=validation_score,wrong_bin_rejected=True,sf=sf,symbols=64,wrong_initial_bin_errors=wrong_errors,tracked_symbol_errors=tracked_errors,final_tracking_hz=estimates[-1],duration_s=duration,drift_end_hz=drift_bins*bin_hz,
            drift_hz_per_s=slope,symbol_errors=len(bad),first_error_symbol=int(bad[0]) if len(bad) else None,
            training_estimate_hz=estimated,training_coherence=coherence,
            scope='Explicit linear external-channel drift through reduced TX/RX; frozen chip rails and sample clock, known synthetic training timing, training-only versus decision-directed tracking.'))
    return rows


def short_burst_clock_checks():
    """Reuse serial transition tracker at 480 Mb/s with short generic training."""
    from recovered_clock import receive
    from framing import Framer,MARKER
    rows=[];rng=np.random.default_rng(931)
    payload=usb_nrzi(rng.integers(0,2,512).tolist())
    for training_length in (8,32):
        levels=np.r_[np.arange(training_length)%2,payload]
        for phase in (-.45,.45,.7):
            for ppm in (-500,500):
                times,indices,decoded,states=receive(2*levels-1,480e6,phase,ppm)
                valid=(indices>=training_length)&(indices<len(levels))
                selected=indices[valid]
                errors=int(np.count_nonzero(decoded[valid]!=levels[selected]))
                missing=int(len(levels)-training_length-len(np.unique(selected)))
                framed_levels=np.r_[np.arange(training_length)%2,MARKER,payload]
                _,_,framed_bits,_=receive(2*framed_levels-1,480e6,phase,ppm)
                framer=Framer();observed=[]
                for bit in framed_bits:
                    word=framer.feed(int(bit))
                    if word is not None:observed.extend((word>>j)&1 for j in range(10))
                observed.extend((framer.value>>j)&1 for j in range(framer.count))
                framed_errors=sum(a!=b for a,b in zip(observed,payload))
                framed_missing=len(payload)-len(observed)
                damaged=list(MARKER);damaged[17]^=1
                _,_,damaged_bits,_=receive(2*np.r_[np.arange(training_length)%2,damaged,payload]-1,480e6,phase,ppm)
                bad_framer=Framer()
                for bit in damaged_bits:bad_framer.feed(int(bit))
                assert bad_framer.state!='PAYLOAD'
                rows.append(dict(training_bits=training_length,phase_ui=phase,period_ppm=ppm,
                    synthetic_marker_acquired=framer.state=='PAYLOAD',marker_payload_errors=framed_errors,marker_missing_samples=framed_missing,damaged_marker_rejected=True,
                    payload_line_bits=len(payload),line_bit_errors=errors,missing_payload_samples=missing,
                    final_period_ppm=float(states[-1,1]),
                    scope='Generic alternating prefix and stuffed NRZI levels; ideal first-order channel crossings, near-nominal oscillator, evaluation-only initial cycle labels; no burst detector, USB sync/EOP or physical pad/CDR coupling.'))
    return rows


def release_holdback(times, volts, samples, ui, capacity=4):
    """Replay observed samples with finite storage; never retract committed bits.

    Samples become available at the next observation tick. Release detection uses
    only the current/past pad observations. This is an FPGA-side diagnostic,
    not yet the canonical chip event path or a USB EOP detector.
    """
    from collections import deque
    pending=deque();committed=[];next_sample=0;low_since=None;started=False
    spacing=float(np.max(np.diff(times)));delay=.5*ui+2*spacing
    maximum_pending=0;discarded=0;boundary=None
    for time,value in zip(times,volts):
        if abs(value)>=.1:started=True;low_since=None
        elif started and low_since is None:low_since=float(time)
        while next_sample<len(samples) and samples[next_sample][0]<=time:
            if len(pending)>=capacity:raise OverflowError('release holdback full')
            pending.append(samples[next_sample]);next_sample+=1
            maximum_pending=max(maximum_pending,len(pending))
        if low_since is not None and time-low_since>=.5*ui:
            assert all(t<low_since for _,t,_ in committed),'Already committed release sample'
            for sample_time,bit in pending:
                if sample_time<low_since:committed.append((float(time),sample_time,bit))
                else:discarded+=1
            pending.clear();boundary=float(time);break
        while pending and time-pending[0][0]>=delay:
            sample_time,bit=pending.popleft()
            committed.append((float(time),sample_time,bit))
    return committed,dict(boundary_s=boundary,maximum_pending=maximum_pending,
        discarded_release_samples=discarded,holdback_s=delay,
        pending_at_stop=len(pending))


def pad_burst_clock_checks():
    """Loaded pad observations establish timing origin; synthetic framing only."""
    from framing import Framer,MARKER
    from clock_tracking_screen import track
    control_times=np.arange(33)/8
    control_volts=np.ones(33);control_volts[8:11]=0.;control_volts[24:]=0.
    control_samples=[(float(t),int(i%2)) for i,t in enumerate(np.arange(.25,4.,.5))]
    emitted,control=release_holdback(control_times,control_volts,control_samples,1.)
    assert control['boundary_s']==3.5 and control['discarded_release_samples']==1
    assert [(t,b) for _,t,b in emitted]==[(t,b) for t,b in control_samples if t<3.]
    assert all(commit>=t for commit,t,_ in emitted)
    try:release_holdback(control_times,control_volts,control_samples,1.,capacity=1)
    except OverflowError:pass
    else:raise AssertionError('Undersized holdback did not fault')
    payload=usb_nrzi(np.random.default_rng(932).integers(0,2,128).tolist())
    levels=np.r_[np.arange(32)%2,MARKER,payload];ui=1/480e6;rows=[]
    for steps in (8,16):
      for idle_ui in (0.,17.37):
        pad=SharedWiredPad();pad.configure('usb','device','hs',True)
        times=[0.];volts=[0.];edges=[];origin=None;launch=0;start=idle_ui*ui
        end=start+len(levels)*ui;low_since=None;observed_end=None;end_confirmed=None
        grid=np.arange(1,int(np.floor((end+4*ui)/(ui/steps)))+1)*ui/steps
        for time in grid:
            while launch<len(levels) and start+launch*ui<=time:
                pad.advance(start+launch*ui)
                pad.drive(peer='J' if levels[launch] else 'K');launch+=1
            if launch==len(levels) and time>=end:
                pad.advance(end);pad.drive();launch+=1
            pad.advance(float(time));value=pad.observe()['differential_v']
            if origin is None and abs(value)>=.1:origin=float(time)
            if origin is not None and observed_end is None:
                if abs(value)<.1:
                    if low_since is None:low_since=float(time)
                    if time-low_since>=.5*ui:
                        observed_end=low_since;end_confirmed=float(time)
                else:low_since=None
            if origin is not None and volts[-1]*value<0:
                edges.append(times[-1]-volts[-1]*(time-times[-1])/(value-volts[-1]))
            times.append(float(time));volts.append(value)
        assert origin is not None and observed_end is not None
        for phase in (-.45,.45):
            relative_edges=np.asarray([e-origin for e in edges if origin<e<end_confirmed])
            _,samples=track(relative_edges,ui,phase,500,sample_until=end_confirmed-origin)
            sample_times=samples[:,0]+origin
            sample_bits=(np.interp(sample_times,times,volts)>0).astype(int)
            committed,holdback=release_holdback(times,volts,list(zip(sample_times,sample_bits)),ui)
            assert holdback['boundary_s']==end_confirmed and holdback['pending_at_stop']==0
            observed=[bit for _,_,bit in committed]
            framer=Framer();decoded=[]
            for bit in observed:
                word=framer.feed(int(bit))
                if word is not None:decoded.extend((word>>j)&1 for j in range(10))
            decoded.extend((framer.value>>j)&1 for j in range(framer.count))
            errors=sum(a!=b for a,b in zip(decoded,payload));missing=len(payload)-len(decoded)
            assert framer.state=='PAYLOAD' and errors==0 and missing==0
            rows.append(dict(samples_per_ui=steps,idle_ui=idle_ui,detected_origin_s=origin,
                detection_delay_s=origin-start,end_observed_s=observed_end,end_confirmed_s=end_confirmed,end_confirmation_delay_s=end_confirmed-end,phase_ui=phase,period_ppm=500,
                observed_crossings=len(edges),payload_line_bits=len(payload),errors=errors,missing=missing,holdback=holdback,
                scope='Finite pad, fixed rail and global observation grid; first 0.1 V magnitude observation starts PI timing. Half-UI low-magnitude qualification identifies release; four-entry holdback delays commitment and discards release samples before delivery. Synthetic marker/release only, not USB EOP; no noise or canonical event integration.'))
    return rows


def trained_receiver_checks():
    from receiver_impairments import Frontend
    rows=[]
    service=make_chip(protocol='wifi_he20').protocol_service
    # Synthetic known training, not an 802.11 preamble. Held-out data use a
    # separate random source and are never passed to the estimator.
    training=np.random.default_rng(900).integers(0,2,234*2)
    for seed in (81,82,83):
        payload=np.random.default_rng(seed).integers(0,2,234*10)
        for gi in (.8,3.2):
            w=he20(np.r_[training,payload],gi_us=gi)
            split=2*(256+w.metadata['cp'])
            bins=np.asarray(w.metadata['data'])%256
            phase=.04*np.sin(2*math.pi*1e6*np.arange(len(w.samples))/w.sample_hz)
            for bits in (8,12):
                combined=dict(gain_error=.02,phase_error=.03,saturation=.3,noise_rms=.0003,seed=seed)
                cases=[('nominal',{},1.,False),('iq',dict(gain_error=.02,phase_error=.03),1.,False),
                    ('compression',dict(saturation=.3),1.,False),('noise',dict(noise_rms=.0003,seed=seed),1.,False),
                    ('frontend',combined,1.,False),('frontend_and_lo',combined,1.,True),
                    ('frontend_and_lo_half_gain',combined,.5,True)]
                for condition,settings,gain,phase_enabled in cases:
                    service.chip.configure_rx_gain(gain)
                    service.chip.frontend=Frontend(**settings)
                    kwargs=dict(tx_phase_rad=phase,rx_phase_rad=-phase) if phase_enabled else {}
                    z,clipped=service.project_link(w,bits=bits,**kwargs)
                    if condition=='nominal':baseline=z.copy()
                    else:assert np.any(z!=baseline)
                    eq=TrainedBlockEqualizer(256,w.metadata['cp'],bins)
                    reject(lambda:eq.observe(z[split:]))
                    try:eq.train(w.samples[:split],z[:split])
                    except ValueError as error:
                        if bits==12 and condition=='nominal':raise
                        reject(lambda:eq.observe(z[split:]))
                        rows.append(dict(profile='wifi_he20',seed=seed,guard_us=gi,converter_bits=bits,
                            condition=condition,rx_gain=gain,frontend_parameters=settings,
                            training_symbols=468,held_out_symbols=len(payload),symbol_errors=None,
                            evm_rms=None,quality_status='open',training_rejected=str(error),
                            scope='Insufficient synthetic training estimate; payload not admitted'))
                        continue
                    frozen=eq.response.copy()
                    observed=eq.observe(z[split:])
                    errors=int(np.count_nonzero((observed.real>0).ravel()!=payload))
                    reference=eq.spectrum(w.samples[split:])  # Scoring only, after observation.
                    evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
                    if bits==12 and condition=='nominal':assert errors==0,(seed,gi,errors)
                    assert clipped==0 and np.array_equal(eq.response,frozen)
                    assert np.count_nonzero((eq.observe(-z[split:]).real>0).ravel()!=payload)>len(payload)//2
                    reject(lambda:eq.train(w.samples[:split],np.zeros(split,complex)))
                    reject(lambda:eq.observe(z[split:]))
                    rows.append(dict(profile='wifi_he20',seed=seed,guard_us=gi,converter_bits=bits,
                        condition=condition,rx_gain=gain,frontend_parameters=settings,
                        lo_phase_peak_rad=.04 if kwargs else 0.,
                        training_symbols=468,held_out_symbols=len(payload),symbol_errors=errors,
                        evm_rms=evm,quality_status='open' if errors else 'finite_fixture_pass',
                        scope='external FPGA equalizer, synthetic known training, held-out BPSK data, fixed timing/zero CFO; declared impairments, frozen rails'))
    # Diagnose the previously failing EDR fixture without changing chip defaults.
    service=make_chip(protocol='bluetooth_br_edr').protocol_service
    for seed in (81,82,83):
        w=service.waveform('edr3',seed)
        for amplitude in (.1,.2,.3):
            z,clipped=service.project_link(w,bits=8,amplitude=amplitude)
            errors=int(np.count_nonzero(decisions(w,z)!=w.symbols))
            assert clipped==0
            rows.append(dict(profile='bluetooth_br_edr',variant='edr3',seed=seed,
                converter_bits=8,dac_amplitude=amplitude,symbol_errors=errors,
                quality_status='open' if errors else 'finite_fixture_pass',
                scope='headroom diagnostic; unchanged defaults, no acquisition/noise margin qualification'))
    return rows


def carrier_recovery_checks():
    service=make_chip(protocol='wifi_he20').protocol_service;rows=[]
    training=np.random.default_rng(900).integers(0,2,234)
    for seed in (81,82,83):
        payload=np.random.default_rng(seed).integers(0,2,234*10)
        w=he20(np.r_[training,training,training,payload]);length=272
        bins=np.asarray(w.metadata['data'])%256
        for offset in (-20000.,0.,20000.):
            for noise in (0.,.0001):
                z,clipped=service.project_link(w,bits=12,frequency_offset_hz=offset,
                                              noise_rms=noise,seed=seed)
                # First repeated block absorbs startup. Estimate from received
                # training only; neither injected CFO nor payload is an input.
                estimated,coherence=repeated_training_frequency(z[length:3*length],length,w.sample_hz)
                corrected=z*np.exp(-2j*math.pi*estimated*np.arange(len(z))/w.sample_hz)
                eq=TrainedBlockEqualizer(256,16,bins)
                eq.train(w.samples[length:3*length],corrected[length:3*length])
                observed=eq.observe(corrected[3*length:])
                errors=int(np.count_nonzero((observed.real>0).ravel()!=payload))
                reference=eq.spectrum(w.samples[3*length:])
                evm=float(np.sqrt(np.mean(abs(observed-reference)**2)/np.mean(abs(reference)**2)))
                assert errors==0 and clipped==0,(seed,offset,noise,errors)
                # Same estimator with correction disabled must expose the CFO.
                eq.train(w.samples[length:3*length],z[length:3*length])
                uncorrected=int(np.count_nonzero((eq.observe(z[3*length:]).real>0).ravel()!=payload))
                if offset:assert uncorrected>0
                rows.append(dict(seed=seed,converter_bits=12,injected_offset_hz=offset,
                    estimated_offset_hz=estimated,noise_rms_v=noise,coherence=coherence,
                    held_out_symbols=len(payload),symbol_errors=errors,evm_rms=evm,
                    correction_disabled_errors=uncorrected,
                    scope='synthetic repeated training, known block boundary, fine CFO only; frozen rails'))
    reject(lambda:repeated_training_frequency(np.zeros(544),272,20e6))
    rng=np.random.default_rng(901)
    reject(lambda:repeated_training_frequency(rng.normal(size=544)+1j*rng.normal(size=544),272,20e6))
    # Explicit ambiguity control: high coherence cannot distinguish aliased CFO.
    fs=20e6;lag=272;true_offset=.75*fs/lag
    tone=np.exp(2j*math.pi*true_offset*np.arange(2*lag)/fs)
    aliased,_=repeated_training_frequency(tone,lag,fs)
    assert abs(aliased-(true_offset-fs/lag))<1e-8
    return dict(cases=rows,unambiguous_offset_limit_hz=fs/(2*lag),
                coarse_acquisition_implemented=False,alias_negative_control=True)


def line_and_timing_checks():
    rng=np.random.default_rng(901);bits=np.r_[np.ones(30,int),rng.integers(0,2,200)].tolist()
    levels=usb_nrzi(bits)
    assert usb_decode(levels)==bits
    reject(lambda:usb_decode([1]*7))
    assert len(levels)>len(bits)
    rows=[]
    for role in ('host','device'):
        pad=SharedWiredPad();pad.configure('usb',role,'fs',True);pad.advance(100e-9)
        assert pad.observe()['j'] and pad.voltage[0]>2.8
        pad.drive(local='SE0');pad.advance(120e-9)
        assert pad.observe()['se0']
        reject(lambda:pad.drive('J','K'))
        reject(lambda:pad.configure('usb',role,'hs',True))
        pad.drive();pad.configure('usb',role,'hs',True)
        decoded=[]
        for level in levels:
            pad.drive(local='J' if level else 'K');pad.advance(pad.time+1/480e6)
            assert abs(pad.observe()['differential_v'])>.35
            decoded.append(int(pad.observe()['j']))
        assert usb_decode(decoded)==bits
        pad.drive();pad.advance(pad.time+10e-9);assert pad.observe()['squelch']
        rows.append(dict(role=role,hs_bits=len(bits),encoded_symbols=len(levels),bit_errors=0,
            fs_attach_and_reset=True,turnaround_requires_release=True,
            scope='finite pad with ideal external source; no packet/chirp handshake/clock recovery'))
    for kind in ('reset','init','wake'):
        seq=sata_oob(kind)
        assert detect_oob(seq)==('wake' if kind=='wake' else 'reset_or_init')
        damaged=seq.copy();damaged[2]=(damaged[2][0],damaged[2][1]+100e-9)
        assert detect_oob(damaged) is None
    # Same assumed FPGA decision cost; only host service waiting changes.
    params=dict(word_hz=300e6,rx_words=2,tx_words=2,fpga_s=40e-9,turnaround_s=10e-9,deadline_s=100e-9)
    fast=response_budget(**params);bulk=response_budget(**params,framed=True)
    assert fast['met'] and not bulk['met']
    stalled=response_budget(**params,queue_words=100)
    assert not stalled['met']
    # Numerical example, not a selected USB normative timing limit.
    return dict(usb=rows,sata_oob_negative_controls=True,
        illustrative_deadline_s=100e-9,deadline_stream=fast,framed=bulk,stalled=stalled)


def usb_reuse_checks():
    from stream_codec import encode, Receiver, slots
    from transport_model import simulate
    from fractions import Fraction
    rows=[]
    for role in ('host','device'):
        c=make_chip(protocol='usb2');c.protocol_service.select('usb2',role)
        receiver=c.protocol_service.usb_transport()
        got=[];expected=[]
        for frame in range(130):
            payload=[(frame*13+i)&1023 for i in range(frame%4)]
            expected.extend(payload)
            words=encode(0,payload,[],frame%64,frame_words=8)
            assert len(words)==8
            for w in words:
                event=receiver.feed(w)
                if event and event[0]=='wire':got.append(event[1])
        assert got==expected and receiver.sequence==2
        reject(lambda:encode(0,[0]*4,[],0,frame_words=8))
        bad=encode(0,[17],[],0,frame_words=8);bad[0]^=1
        r=Receiver(0,frame_words=8)
        reject(lambda:[r.feed(x) for x in bad])
        assert r.fault
        rows.append(dict(role=role,frames=130,payload_words=len(got),sequence_wrap=True,header_corruption_rejected=True))
    bound=usb_framed_turnaround();old=usb_framed_turnaround(frame_words=64)
    assert bound['meets_bound'] and not old['meets_bound']
    assert bound['raw_payload_capacity_bps']>480e6
    assert not usb_framed_turnaround(fpga_s=200e-9)['meets_bound']
    assert usb_framed_turnaround(fpga_s=0,analog_s=0)['minimum_guard_s']==8/480e6
    queues=[]
    for phase in (Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(999,1000)):
        queues.append(simulate(slots(0,8),'wire',480000000,10,250000000,
                              phase=phase,frames=256,startup_words=64,streaming=True))
    # Explicit frame-phase response sweep with independent host clock phases.
    # Sample just-after snapshot boundaries as well as exact boundaries.
    worst=0.
    def transfer(t,origin):
        f=8/250e6
        snap=origin+math.ceil((t-origin)/f)*f
        return snap+2*f  # following frame, conservatively final payload word
    for rx_phase in np.linspace(0,8/250e6,65):
        for tx_phase in np.linspace(0,8/250e6,65):
            start=1e-6+rx_phase
            decision=transfer(start,0)+40e-9
            end=transfer(decision,tx_phase)+34e-9+(4+4)/250e6+20/480e6
            worst=max(worst,end-start)
    assert worst<=bound['worst_s']+1e-15
    return dict(codec=rows,bound=bound,old_frame_bound=old,phase_sweep_worst_s=worst,
                queues=queues,scope='existing codec/scheduler reused; continuous traffic and bounded response assumptions, not RTL/USB compliance')


def short_frame_lifecycle_checks():
    from wired_return_lifecycle import DuplexChip
    from host_activation import HostActivation
    from stream_codec import encode
    rows=[]
    for role in ('host','device'):
        c=make_chip(protocol='usb2');s=c.protocol_service;s.select('usb2',role)
        reject(lambda:s.configure_transport(1))
        assert c.state=='reset'
        s.configure_transport(0)
        assert c.state=='acquiring' and not c.session.armed
        assert c.channel.rate==480e6 and c.host_frame_words==8
        assert abs(c.wire_pll.divider*c.wire_pll.reference_hz-480e6)<1e-6
        assert len(c.receiver.plan)==8 and c.host_quota('wire')==3 and c.host_quota('iq')==0
        reject(lambda:c.accept_wire(1))  # No serial bypass of missing USB adapter.
        reject(lambda:c.start_wire_return(c.time+1e-9))  # No fabricated lock.
        c.set_reference(False,c.time)
        c.acknowledge_host_abort(c.epoch,c.time);c.acknowledge_drain(c.epoch,c.time)
        s.select('sata_gen1')
        assert c.host_frame_words==64 and c.wire_rate_override==1.5e9
        rows.append(dict(role=role,canonical_configuration=True,usb_packet_path_blocked=True,
                         stopped_profile_restores_frame_geometry=True))
    # Same timed lifecycle in a fast component fixture. Its ideal acquisition
    # is not substituted for canonical clock qualification.
    c=DuplexChip(watchdog_s=20e-6);c.host_frame_words=8;c.wire_rate_override=480e6
    c.configure(0,0);c.advance(c.acquisition_s)
    expected=[17,801,99]
    c.incoming_wire(expected,c.time,ppm=0);c.capture(0,c.time+1e-9)
    c.advance(c.time+10e-6)
    assert c.host_wire==expected and c.return_ticks>512
    c.quiesce(c.time,'short-frame abort')
    assert not c.return_frame and not c.wired_return and math.isinf(c.next_return)
    epoch=c.epoch;c.acknowledge_host_abort(epoch,c.time);c.acknowledge_drain(epoch,c.time)
    assert c.epoch==epoch+1 and c.state=='reset'
    # Preserve the existing 4096-edge conditioning duration, including sequence
    # wrap. Only frame counter/quotas change; no shortened bias-settle claim.
    a=HostActivation();a.start(0,0,7,frame_words=8)
    for frame in range(512):
        words=encode(0,[],[],frame%64,frame_words=8)
        for i in range(5,8):words[i]=words[i-1]^1023
        for i,word in enumerate(words):a.feed(word,(frame*8+i+1)*a.period,7)
    assert a.state=='ready' and a.words==4096 and a.ready(a.last,7)
    assert not a.ready(a.last,8)
    damaged=HostActivation();damaged.start(0,0,0,frame_words=8)
    words=encode(0,[],[],0,frame_words=8);words[0]^=1
    for i,word in enumerate(words[:4]):damaged.feed(word,(i+1)*damaged.period,0)
    reject(lambda:damaged.feed(words[4],5*damaged.period,0))
    return dict(canonical=rows,component_return_words=len(expected),training_words=a.words,
                scope='canonical configuration/guards plus component timed return and training; no USB packet/CDR or canonical active traffic')


def generic_configuration_checks():
    c=make_chip()
    # The sidecar is only a compatibility fixture for protocol examples. The
    # actual chip API must operate with all named-protocol metadata removed.
    del c.protocol_service;del c.protocol_requirements
    c.configure_resources(engine='wire',line_rate_bps=1.62e9,frame_words=64,
                          tx_enabled=True,rx_enabled=True)
    assert not hasattr(c,'protocol_id')
    c.require_wire_direction('tx');c.require_wire_direction('rx')
    before=(c.active_engine,c.wire_rate_override,c.host_frame_words)
    reject(lambda:c.configure_resources(engine='rf',line_rate_bps=1.5e9))
    assert before==(c.active_engine,c.wire_rate_override,c.host_frame_words)
    c.configure_resources(engine='wire',line_rate_bps=1.5e9,frame_words=8,
                          tx_enabled=False,rx_enabled=True)
    reject(lambda:c.require_wire_direction('tx'));c.require_wire_direction('rx')
    reject(lambda:c.configure(1,c.time));assert c.state=='reset'
    c.configure_resources(engine='wire',line_rate_bps=480e6,pad_path='bidirectional',frame_words=8)
    reject(lambda:c.require_wire_direction('rx'))
    c.configure_resources(engine='rf')
    assert c.host_frame_words==64 and c.wire_rate_override is None
    # Raw ownership transfer must obey pad isolation even without test recipes.
    pad=SharedWiredPad();pad.time=c.time;c.analog_owner.pad_branch=pad
    c.configure_resources(engine='wire',line_rate_bps=480e6,pad_path='bidirectional')
    pad.configure('usb','device','hs',True)
    for local,remote in [('J','Z'),('Z','K')]:
        pad.drive(local,remote)
        generation=c.resource_generation
        reject(lambda:c.select_engine('rf'))
        assert c.active_engine=='wire' and c.resource_generation==generation
        assert (pad.local,pad.peer)==(local,remote)
        pad.drive()
    voltage=pad.voltage.copy()
    c.select_engine('rf');assert c.resource_generation>generation
    assert pad.mode=='isolated' and np.array_equal(pad.voltage,voltage)
    # Saved host settings are invalidated by generic configuration, not just
    # selecting another named test recipe.
    other=make_chip(protocol='bluetooth_le');service=other.protocol_service
    service.save_context(0,2.44e9)
    other.configure_resources(engine='rf')
    reject(lambda:service.request_hop(0))
    return dict(protocol_metadata_required=False,independent_rate_direction_framing=True,
                invalid_combinations_rejected=True,raw_handover_isolation=True,
                stale_host_context_rejected=True,
                scope='configuration/ownership only, not active traffic or arbitrary silicon rates')


def serial_checks():
    rows=[]
    for profile,role in [('pcie_gen1','endpoint'),('ethernet_1000basex','link'),('sgmii','link'),('sata_gen1','host'),('sata_gen1','device'),
                         ('displayport_rbr','source'),('displayport_rbr','sink')]:
        c=make_chip(protocol=profile);c.protocol_service.select(profile,role)
        c.protocol_service.configure_transport(1)
        rate=c.protocol_service.selected['line_rate_bps']
        assert c.channel.rate==rate
        assert abs(c.wire_pll.divider*c.wire_pll.reference_hz-rate)<1e-6
        assert c.serializer.pll is c.wire_pll and not c.rf_pll.powered
        reject(lambda:c.protocol_service.select('usb2'))
        if profile=='sata_gen1':
            assert detect_oob(c.protocol_service.oob('reset' if role=='host' else 'init'))=='reset_or_init'
            reject(lambda:c.protocol_service.oob('init' if role=='host' else 'reset'))
        # Fast clock/channel reduction explicitly freezes rail forcing; actual
        # canonical construction/ownership is checked above, not impersonated.
        pll=copy.copy(c.wire_pll);pll.supply_trajectory=None
        for tick in range(1,401):pll.advance(tick/40e6);pll.observe_lock()
        assert pll.locked,(profile,pll.frequency_hz)
        channel=copy.deepcopy(c.channel)
        # Exercise the common receive-event constructor at this profile's rate.
        # This is a component check with its normal lifecycle, not canonical lock.
        from wired_return_lifecycle import DuplexChip
        receiver=DuplexChip(watchdog_s=20e-6)
        receiver.wire_rate_override=rate
        receiver.configure(1,0);receiver.advance(receiver.acquisition_s)
        receiver.incoming_wire([17,801,99],receiver.time,ppm=0)
        times=[event[0] for event in receiver.rx_events]
        assert len(times)==3
        assert np.allclose(np.diff(times),10/rate,rtol=1e-4,atol=1e-12)
        serial=PLLSerializer(channel,pll.time,pll)
        words=[0x155,0x2aa,0,1023,0x17b,0x306]
        got=[]
        for word in words:
            serial.start(word,serial.time+1/rate,1/rate)
            while serial.active:
                result=serial.step()
                if result is not None:got.append(result)
        assert got==words
        serial.accounting()
        rows.append(dict(profile=profile,role=role,rate_bps=rate,words=len(got),
                         clock_locked=True,scope='canonical rate wiring plus frozen-rail PLL/serializer reduction; no CDR or peer training'))
    return rows


def oob_observation_checks():
    service=make_chip(protocol='sata_gen1').protocol_service
    rows=[]
    def run(kind,*,tau=10e-9,amplitude=.4,split=False,intervals=None):
        d=service.oob_receiver(tau_s=tau)
        seq=sata_oob(kind) if intervals is None else intervals
        for a,b in seq:
            if split:
                for t in np.linspace(d.time,a,7)[1:]:d.advance(float(t))
            d.drive(amplitude,a)
            if split:
                for t in np.linspace(a,b,11)[1:]:d.advance(float(t))
            d.drive(0.,b)
        assert not d.events,'Do not complete a burst train before final quiet interval'
        d.advance(seq[-1][1]+2e-6)
        return d
    for kind in ('reset','init','wake'):
        for tau in (2e-9,10e-9):
            a=run(kind,tau=tau);b=run(kind,tau=tau,split=True)
            assert len(a.events)==len(b.events)==1
            event=a.events[0]
            assert event['kind']==('wake' if kind=='wake' else 'reset_or_init')
            assert event['bursts']==6
            assert abs(event['time_s']-b.events[0]['time_s'])<1e-18
            release=175e-9 if kind=='wake' else 525e-9
            assert event['time_s']>sata_oob(kind)[-1][1]+release
            # First-order rise crossing: independent closed-form calibration.
            probe=service.oob_receiver(tau_s=tau);probe.drive(.4,0);probe.advance(50e-9)
            assert abs(probe.rise+tau*math.log(1-.12/.4))<1e-20
            rows.append(dict(kind=kind,tau_s=tau,observed_bursts=6,
                completion_s=event['time_s'],partition_invariant=True))
        assert not run(kind,amplitude=.05).events
        assert not run(kind,intervals=sata_oob(kind)[:3]).events
        assert not run(kind,tau=25e-9).events  # Exposes candidate bandwidth failure.
        bad=sata_oob(kind);a,b=bad[2];bad[2]=(a,a+20e-9)
        assert not run(kind,intervals=bad).events
    d=service.oob_receiver();d.drive(.4,0);d.advance(10e-6)
    assert not d.events  # Continuous data activity is not an OOB train.
    reject(lambda:d.drive(float('nan'),d.time))
    reject(lambda:d.advance(d.time-1e-9))
    return dict(cases=rows,negative_controls=['weak input','only three bursts',
        'slow envelope','short middle burst','continuous activity','invalid time/input'],
        scope='causal rectified-envelope RC/comparator/timer reduction; no actual SATA carrier or peer startup',
        candidate_failure='25 ns envelope time constant fails the current timing windows',
        source='https://www.seagate.com/support/disc/manuals/sata/sata_im.pdf section 6.7.4')


def sata_startup_checks():
    import heapq
    from protocol_pad import SataOobStartup
    rows=[]
    for amplitude,tau,drop in ((.4,2e-9,False),(.4,10e-9,False),(.05,10e-9,False),(.4,25e-9,False),(.4,10e-9,True)):
        peers=[SataOobStartup('host',detector_tau_s=tau),SataOobStartup('device',detector_tau_s=tau)]
        for peer in peers:peer.start()
        queue=[];sent=[0,0]
        for step in range(1000):
            for i,peer in enumerate(peers):
                for tx in peer.transmissions[sent[i]:]:
                    assert tx['start_s']>=peer.time,'Controller scheduled a response in the past'
                    if drop and i==1 and tx['kind']=='wake':continue
                    for a,b in tx['intervals']:
                        heapq.heappush(queue,(a,1-i,amplitude));heapq.heappush(queue,(b,1-i,0.))
                sent[i]=len(peer.transmissions)
            time=min(queue[0][0] if queue else math.inf,*(peer.next_event for peer in peers))
            if not math.isfinite(time):break
            for peer in peers:peer.advance(time)
            while queue and queue[0][0]==time:
                _,i,voltage=heapq.heappop(queue);peers[i].drive_received(voltage,time)
        else:raise AssertionError('Startup scheduler failed to terminate')
        states=[peer.state for peer in peers]
        if amplitude==.4 and tau<=10e-9 and not drop:
            assert all(peer.oob_completed_at is not None for peer in peers)
            assert states==['fault']*2  # No ALIGN follows: full startup must time out.
            assert all(peer.fault_reason=='startup timeout' for peer in peers)
            assert [[tx['kind'] for tx in peer.transmissions] for peer in peers]==[['reset','wake'],['init','wake']]
            assert [e['kind'] for e in peers[0].history]==['reset_or_init','wake']
            assert [e['kind'] for e in peers[1].history]==['reset_or_init','wake']
        else:assert peers[0].state=='fault'
        assert not any(peer.phy_ready for peer in peers)
        rows.append(dict(amplitude_v=amplitude,tau_s=tau,drop_device_wake=drop,states=states,
            histories=[peer.history for peer in peers],scheduler_events=step,phy_ready=False,
            oob_completed_at=[peer.oob_completed_at for peer in peers],
            fault_reasons=[peer.fault_reason for peer in peers]))
    guard=SataOobStartup('host');guard.start()
    reject(lambda:guard.advance(guard.deadline+1e-9))
    guard.advance(guard.deadline);assert guard.state=='fault'
    # Feed actual envelopes to a device observer; a new OOB after wake must
    # invalidate unfinished alignment rather than be silently ignored.
    peer=SataOobStartup('device');peer.start()
    def advance_to(t):
        while peer.next_event<t:peer.advance(peer.next_event)
        peer.advance(t)
    def deliver(kind,start):
        for a,b in sata_oob(kind):
            advance_to(start+a);peer.drive_received(.4,start+a)
            advance_to(start+b);peer.drive_received(0.,start+b)
        advance_to(start+b+1e-6)
    deliver('reset',0);assert peer.state=='wait_wake'
    deliver('wake',10e-6);assert peer.state=='await_alignment'
    completed=peer.oob_completed_at;sent=len(peer.transmissions)
    deliver('wake',20e-6)
    assert peer.state=='fault' and peer.fault_reason=='unexpected OOB during startup'
    deliver('reset',30e-6)
    assert peer.state=='fault' and len(peer.transmissions)==sent
    assert peer.oob_completed_at==completed and not peer.phy_ready
    return dict(cases=rows,scope='external FPGA OOB ordering through causal envelope observers; no canonical chip coupling or data link',
        missing_alignment_timeout=True,unexpected_oob_fault=True,sticky_fault=True,
        assumptions=['100 ns local reaction and 100 us overall timeout are exploration budgets, not normative limits.',
            'No ALIGN, D10.2, calibration, retries, power management or canonical acquired traffic.'])


def serial_receive_checks():
    from live_wired_lifecycle import LiveWireChip
    rows=[]
    words=[(i*37+19)%1024 for i in range(80)]
    for profile in ('pcie_gen1','ethernet_1000basex','sgmii','sata_gen1','displayport_rbr'):
        c=make_chip(protocol=profile);rate=c.protocol_service.selected['line_rate_bps']
        for phase in (-.3,.3):
            for ppm in (-100,100):
                # Use the canonical receiver factory and its actual configured
                # equalizer parameters, but freeze supply forcing in this reduction.
                rx=c.make_receiver(words,rate,0,phase,ppm);got=[]
                while not rx.done:
                    value=rx.step()
                    if value is not None:got.append(value)
                assert got==words,(profile,phase,ppm,len(got))
                assert rx.transitions>0 and rx.framer.state=='PAYLOAD'
                rows.append(dict(profile=profile,rate_bps=rate,phase_ui=phase,ppm=ppm,
                    words=len(got),samples=rx.samples,transitions=rx.transitions,
                    scope='canonical receiver factory, causal edge tracking; frozen rail, synthetic training/marker'))
        # Exercise rate dispatch through the real live lifecycle, rather than
        # passing a correct rate directly and missing a hardcoded caller.
        component=LiveWireChip(watchdog_s=20e-6)
        component.wire_rate_override=rate;component.configure(1,0)
        component.advance(3e-6);assert component.state=='active'
        component.incoming_wire(words,component.time)
        assert math.isclose(component.live_rx.ui,1/rate,rel_tol=1e-12)
        component.advance(component.time+3e-6)
        assert list(component.wired_return)==words
        # Disturb only future sampling after a decoded prefix; detect loss rather
        # than using expected bits to repair alignment.
        rx=c.make_receiver(words,rate,0,.3,100);damaged=[]
        while len(damaged)<20 and not rx.done:
            value=rx.step()
            if value is not None:damaged.append(value)
        assert damaged==words[:20]
        rx.disturb(rx.time,1.1,0)
        while not rx.done:
            value=rx.step()
            if value is not None:damaged.append(value)
        assert damaged[:20]==words[:20] and damaged!=words
    return dict(cases=rows,live_dispatch_checked=True,phase_slip_negative_controls=5,
                protocol_training=False,physical_bandwidth_qualified=False,
                limitations=['Channel pole scales with requested rate; this is not evidence of transistor bandwidth.',
                    'Ideal crossing timestamps, test-link marker, no real PCS/peer negotiation or SSC.',
                    'No canonical acquired supply-coupled packet traffic or BER envelope.'])


def coupled_checks():
    rows=[]
    for role in ('host','device'):
        c=make_chip(protocol='usb2');c.protocol_service.select('usb2',role)
        service=c.protocol_service;service.usb_mode('hs');pad=c.analog_owner.pad_branch
        initial=pad.energy()
        assert service.usb_hold(1e-9,local='J')['differential_v']>.35
        rail=float(c.analog_owner.domains.voltage[3]);assert rail<3.3
        assert service.usb_hold(1e-9,local='K')['differential_v']<-.35
        reject(lambda:service.usb_hold(1e-9,local='J',peer='K'))
        reject(lambda:service.select('sata_gen1'))
        service.usb_hold(1e-9)
        assert service.usb_hold(1e-9,peer='J')['differential_v']>.35
        residual=pad.source_energy_j+pad.external_energy_j-pad.dissipated_j-(pad.energy()-initial)
        assert abs(residual)<1e-18,residual
        assert pad.time==c.time==c.analog_owner.time==c.analog_owner.host_bank.time
        assert pad.external_energy_j>0 and pad.source_energy_j>0
        service.usb_hold(1e-9)
        before=pad.voltage.copy();service.select('sata_gen1')
        assert np.array_equal(before,pad.voltage),'Profile transition erased capacitor history'
        assert pad.mode=='isolated'
        rows.append(dict(profile='usb2',role=role,coupled_time_s=c.time,
                         minimum_observed_wire_rail_v=rail,pad_energy_residual_j=residual,
                         scope='canonical pad/rail/host-ground ODE, both drive directions; no host packet transport'))
    for profile in ('wifi_he20','bluetooth_le','bluetooth_br_edr','ieee802154_24','lora_24'):
        c=make_chip(protocol=profile);service=c.protocol_service
        complete=service.waveform();carrier=service.selected['carrier_min_hz']
        first=int(np.flatnonzero(abs(complete.samples)>1e-6)[0])
        w=Waveform(complete.samples[first:],complete.sample_hz,complete.kind,complete.symbols,complete.metadata)
        # A nonzero excerpt probes coupling even when a pulse starts at zero.
        service.inject_receive(w,carrier)
        reject(lambda: service.configure_transport(0))  # No bypass of coarse acquisition.
        c.bits=12  # Diagnostic ADC format only; session remains reset/unarmed.
        c.tx.apply_sample(.1*w.samples[0],c.time)
        c.output_network.configure(True,False)
        c.advance(2e-9)
        assert c.tx.rx_bank is c.analog_owner.rx_bank
        assert abs(c.tx.received)>0
        assert c.time==c.analog_owner.time==c.rf_pll.time
        assert c.external_waveform[1] is w
        c.convert_adc(c.tx.received)
        assert c.adc_reference.samples==1 and c.dac_reference.dac_updates==1
        assert abs(c.output_network.voltage[1])>0
        rows.append(dict(profile=profile,coupled_time_s=c.time,received_magnitude=float(abs(c.tx.received)),
            adc_conversions=1,dac_updates=1,excerpt_start_sample=first,scope='finite startup RX and TX coupling; not acquired packet or EVM qualification'))
    return rows


def current_sink_energy_check(rate):
    """Independent quadrature of external source, resistors and sink powers."""
    from wired_blocks import CurrentSwitchChannel
    channel=CurrentSwitchChannel(rate)
    cap=channel.load_tau_s/channel.termination_ohm
    def stored(c):
        pins=c.pin_state()
        return .5*cap*(pins['positive_v']**2+pins['negative_v']**2)
    initial=stored(channel);integrals=np.zeros(3);peak_change=0.;segment_residuals=[]
    nodes,weights=np.polynomial.legendre.leggauss(24)
    # Turn on, alternate, then turn off: both charging and discharging matter.
    for command in (1.,-1.,1.,-1.,0.):
        dt=1/rate;before=stored(channel);previous=integrals.copy()
        for node,weight in zip(nodes,weights):
            trial=copy.copy(channel);trial.advance_state(command,(node+1)*dt/2)
            pins=trial.pin_state()
            integrals+=weight*dt/2*np.array([pins['termination_source_power_w'],
                pins['resistor_power_w'],pins['sink_power_w']])
        channel.advance_state(command,dt)
        segment=integrals-previous;delta=stored(channel)-before
        peak_change=max(peak_change,abs(delta))
        segment_residuals.append(float(segment[0]-segment[1]-segment[2]-delta))
    assert max(abs(x) for x in segment_residuals)<1e-22
    change=stored(channel)-initial
    residual=float(integrals[0]-integrals[1]-integrals[2]-change)
    assert abs(residual)<1e-22,residual
    assert peak_change>1e-13  # Omitting stored charge must be detectable.
    return dict(source_energy_j=float(integrals[0]),resistor_energy_j=float(integrals[1]),
        sink_energy_j=float(integrals[2]),capacitor_energy_change_j=change,residual_j=residual,
        segment_residuals_j=segment_residuals,peak_capacitor_energy_change_j=peak_change)


def multi_chip_video_checks():
    from lane_group import (ForwardedLaneGroup,current_sink_levels,pad_eye,
        forwarded_clock_budget,continuous_framed_lane,forwarded_pll_acquisition,observe_forwarded_payload)
    from stream_codec import encode,Receiver,slots
    rows=[];rng=np.random.default_rng(7531)
    # Opaque FPGA-generated TMDS/control/packet words use the existing framed
    # transport unchanged. This tests all ten bits, not an invented chip codec.
    words=rng.integers(0,1024,(128,3));words[:4,:]=np.array([0b1101010100,0b0010101011,0b0101010100,0b1010101011])[:,None]
    for word_hz,host_mode,host_rate in ((74.25e6,0,250e6),(148.5e6,1,312.5e6)):
        quota=slots(host_mode).count('wire');capacity=host_rate*quota/64
        assert capacity>word_hz
        for lane in range(3):
            decoder=Receiver(host_mode);received=[]
            values=words[:,lane].tolist()
            for seq,start in enumerate(range(0,len(values),quota)):
                for word in encode(host_mode,values[start:start+quota],[],seq):
                    event=decoder.feed(word)
                    if event and event[0]=='wire':received.append(event[1])
            assert received==values
        group=ForwardedLaneGroup(word_hz);reject(lambda:group.arm([True,False,True]));group.arm([True]*3)
        good=group.transfer(words,lane_skew_s=[-.1*group.ui,0.,.1*group.ui],word_delays=[0,2,1],clock_jitter_s=.03*group.ui)
        assert good['word_errors']==0
        bad=group.transfer(words,lane_skew_s=[0.,.6*group.ui,0.],word_delays=[0,0,0])
        assert bad['word_errors']>0
        reject(lambda:group.transfer(words,lane_skew_s=[0.]*3,word_delays=[0,5,0]))
        group.lose_reference(1);reject(lambda:group.transfer(words,lane_skew_s=[0.]*3,word_delays=[0]*3))
        for name in ('dvi_single_link','hdmi_tmds'):
            for role in ('source','sink'):
                chip=make_chip();chip.protocol_service.select(name,role)
                assert chip.active_engine=='wire' and chip.wire_rate_override==1.485e9
                assert chip.wire_interface['clock_source']=='forwarded_word'
                assert chip.wire_interface['electrical']=='dc_current_sink'
                chip.execute_management('configure_wire_interface',0,chip.time)
                assert chip.wire_interface['clock_source']=='embedded'
                chip.execute_management('configure_wire_interface',3,chip.time)
                assert chip.wire_interface['word_reference_hz']==148.5e6
                before=dict(chip.wire_interface)
                reject(lambda:chip.execute_management('configure_wire_interface',4,chip.time))
                assert chip.wire_interface==before
                reject(lambda:chip.configure_wire_interface(clock_source='forwarded_word',word_reference_hz=74.25e6))
                assert chip.wired_tx_enabled==(role=='source') and chip.wired_rx_enabled==(role=='sink')
        bound_chips=[make_chip() for _ in range(3)]
        for chip in bound_chips:
            chip.configure_resources(engine='wire',line_rate_bps=10*word_hz,
                tx_enabled=True,rx_enabled=False)
            chip.execute_management('configure_wire_interface',3,chip.time)
        # Configure real canonical serializer construction at each forwarded rate.
        configured=make_chip()
        configured.configure_resources(engine='wire',line_rate_bps=10*word_hz,
            tx_enabled=True,rx_enabled=False)
        configured.execute_management('configure_wire_interface',3,configured.time)
        configured.configure(host_mode,configured.time)
        assert configured.wire_pll.reference_hz==word_hz
        assert configured.wire_pll.divider==10
        assert configured.serializer.pll is configured.wire_pll
        from wired_blocks import CurrentSwitchChannel
        from wired_serializer import Serializer
        assert isinstance(configured.channel,CurrentSwitchChannel)
        configured.configure_analog_loads()
        assert configured.analog_owner.extra_current(configured.time,3.3)==.002
        power_accounting=configured.wired_power_accounting()
        assert power_accounting['local_bias_current_a']==.002
        assert power_accounting['external_termination_power_w']==0.
        assert power_accounting['return_current_coupled'] and power_accounting['pad_ground_feedback']
        host=configured.analog_owner.host_bank
        g,feed,up,down=host.currents(host.state,host.drive,external_return_a=.008)
        assert abs(g/host.return_r-(float(sum(feed))-float(sum(up))+float(sum(down))+.008))<1e-12
        baseline=host.currents(host.state,host.drive)[0]
        assert g>baseline
        # Short continuous-owner window checks the new ground input reaches
        # rail states without pretending to acquire or run canonical payload.
        owner_base=copy.deepcopy(configured.analog_owner)
        owner_injected=copy.deepcopy(configured.analog_owner)
        owner_base.external_return_current=lambda t:0.
        owner_injected.external_return_current=lambda t:.008
        owner_base.advance(1e-9,0j)
        owner_injected.advance(1e-9,0j)
        rail_change=float(np.max(abs(owner_injected.domains.voltage-owner_base.domains.voltage)))
        assert rail_change>1e-6
        from driver_pll_feedback import inactive_rf_solver
        explicit=copy.deepcopy(configured.analog_owner)
        explicit.external_return_current=lambda t:0.
        assert inactive_rf_solver(explicit)=='RK45'
        explicit.advance(1e-9,0j,rtol=1e-10,atol=1e-13,solver_method='RK45')
        assert np.max(abs(explicit.domains.voltage-owner_base.domains.voltage))<1e-9
        explicit.network.voltage[0]=1e-30
        assert inactive_rf_solver(explicit)=='Radau'
        energy_residuals=[]
        for owner in (owner_base,owner_injected):
            domain=owner.domains;bank=owner.host_bank
            residual=(domain.source_energy_j-domain.feed_loss_j-domain.load_energy_j
                -domain.impulse_energy_j-(bank.cap_energy()-bank.initial_energy))
            assert abs(residual)<1e-18,residual
            energy_residuals.append(float(residual))
        configured.serializer.drive=1.
        configured.configure_analog_loads()
        assert abs(configured.analog_owner.external_return_current(configured.time+1e-9)-.008*(1-math.exp(-10)))<1e-15
        assert configured.analog_owner.external_return_guard(configured.time+1e-9,0.)
        assert not configured.analog_owner.external_return_guard(configured.time+1e-9,3.)
        rejected_owner=copy.deepcopy(configured.analog_owner)
        rejected_owner.external_return_guard=lambda t,g:False
        before_rails=rejected_owner.domains.voltage.copy();before_time=rejected_owner.time
        reject(lambda:rejected_owner.advance(1e-9,0j))
        assert rejected_owner.time==before_time and np.array_equal(rejected_owner.domains.voltage,before_rails)
        configured.serializer.drive=0.
        configured.configure_analog_loads()
        channel=copy.deepcopy(configured.channel)
        serializer=Serializer(channel,0.)
        serializer.start(0x155,0.,1/channel.rate)
        while serializer.active:serializer.step()
        direct=pad_eye([(0x155>>bit)&1 for bit in range(10)],bit_rate=10*word_hz,
            capacitance_f=2e-12,switch_tau_s=100e-12)
        assert channel.errors==0
        pins=channel.pin_state()
        assert pins['current_compliance_valid'] and 2.9<=pins['common_mode_v']<=3.3
        steady=CurrentSwitchChannel(10*word_hz)
        steady.advance_state(1.,20e-9);dc=steady.pin_state()
        assert abs(dc['positive_v']-3.3)<1e-12 and abs(dc['negative_v']-2.9)<1e-12
        assert abs(dc['termination_source_power_w']-dc['resistor_power_w']-dc['sink_power_w'])<1e-15
        shifted=steady.pin_state(.01)
        assert abs(shifted['sink_terminal_power_w']-shifted['sink_power_w']-shifted['ground_transfer_power_w'])<1e-15
        bad_compliance=CurrentSwitchChannel(10*word_hz,termination_v=.5)
        bad_compliance.advance_state(1.,20e-9)
        assert not bad_compliance.pin_state()['current_compliance_valid']
        assert abs(channel.minimum_margin*.4-direct['minimum_signed_eye_v'])<1e-12
        assert not configured.rf_pll.powered
        assert configured.wire_word_phase_target(12.3)==20
        independent=observe_forwarded_payload(configured.wire_pll,words[:16,0],lane_skew_s=25e-12)
        slipped=observe_forwarded_payload(configured.wire_pll,words[:16,0],lane_skew_s=.7/(10*word_hz))
        assert independent['word_errors']==0 and independent['minimum_signed_sample_v']>.1
        assert independent['compliance_valid'] and slipped['word_errors']>0
        # Physically sampled pad words reach finite external deskew buffers.
        # Known first-word alignment is supplied by the FPGA, not inferred from
        # labels or the transmitted payload. Whole-word arrival delay is external.
        captures=[];pad_observers=[]
        for lane,delay in enumerate((0,2,1)):
            observation=observe_forwarded_payload(configured.wire_pll,words[:16,lane],
                lane_skew_s=(lane-1)*25e-12,noise_seed=7531+lane,capture=True)
            captures.append([(t+delay/word_hz,w) for t,w in observation.pop('captures')])
            pad_observers.append(observation)
        causal=ForwardedLaneGroup(word_hz);causal.arm([True]*3)
        aligned=causal.align_captures(captures,epoch=causal.epoch,depth=4)
        assert aligned['fault'] is None and np.array_equal(aligned['words'],words[:16])
        assert all(x['minimum_signed_sample_v']>.1 and x['compliance_valid'] for x in pad_observers)
        assert all(b>a for a,b in zip(aligned['times_s'],aligned['times_s'][1:]))
        shallow=causal.align_captures(captures,epoch=causal.epoch,depth=1)
        assert shallow['fault']=='overflow' and not causal.armed
        reject(lambda:causal.align_captures(captures,epoch=aligned['epoch']))
        causal.arm([True]*3)
        reject(lambda:causal.align_captures(captures,epoch=aligned['epoch']))
        corrupted=[list(c) for c in captures]
        corrupted[1][5]=(corrupted[1][5][0],corrupted[1][5][1]^1)
        damaged_alignment=causal.align_captures(corrupted,epoch=causal.epoch)
        assert damaged_alignment['fault'] is None
        assert np.count_nonzero(damaged_alignment['words']!=words[:16])==1
        # Deskew must preserve corruption, not repair it using expected words.
        causal_pad=dict(rows=len(aligned['words']),maximum_occupancy=aligned['maximum_occupancy'],
            depth=4,observers=pad_observers,overflow_stops_group=True,
            stale_epoch_rejected=True,payload_corruption_preserved=True,
            known_first_word_epoch=True,frozen_supplies=True)
        reject(lambda:configured.configure_wire_interface())
        from live_wired_lifecycle import ForwardedReceiver
        received=[];rx=configured.make_receiver(words[:16,0].tolist(),10*word_hz,0.,0.,0.)
        assert isinstance(rx,ForwardedReceiver) and len(rx.bits)==160
        while not rx.done:
            value=rx.step()
            if value is not None:received.append(value)
        assert received==words[:16,0].tolist() and rx.energy>0
        shifted_rx=configured.make_receiver(words[:16,0].tolist(),10*word_hz,0.,-.4,0.)
        damaged=[]
        while not shifted_rx.done:
            value=shifted_rx.step()
            if value is not None:damaged.append(value)
        assert damaged!=received
        bound_group=ForwardedLaneGroup(word_hz,chips=bound_chips)
        bound_group.arm([True]*3)
        assert bound_group.transfer(words,lane_skew_s=[0.]*3,word_delays=[0]*3)['word_errors']==0
        # Even a change followed by restoration invalidates the launch epoch.
        bound_chips[1].execute_management('configure_wire_interface',0,bound_chips[1].time)
        bound_chips[1].execute_management('configure_wire_interface',3,bound_chips[1].time)
        reject(lambda:bound_group.transfer(words,lane_skew_s=[0.]*3,word_delays=[0]*3))
        assert not bound_group.armed
        bound_group.arm([True]*3)
        bound_chips[2].configure_resources(engine='rf')
        reject(lambda:bound_group.transfer(words,lane_skew_s=[0.]*3,word_delays=[0]*3))
        reject(lambda:bound_group.arm([True]*3))
        acquisition=forwarded_pll_acquisition(word_hz)
        refined=forwarded_pll_acquisition(word_hz,step_divisor=8)
        failed=forwarded_pll_acquisition(word_hz,detuning_fraction=.4)
        assert acquisition['acquired_within_assumed_budget'] and refined['acquired_within_assumed_budget']
        assert not failed['acquired_within_assumed_budget']
        assert abs(acquisition['peak_reference_error_s']-refined['peak_reference_error_s'])<1e-12
        disturbed=forwarded_pll_acquisition(word_hz,noise_rms_hz=20000.,qualification_cycles=128)
        excessive=forwarded_pll_acquisition(word_hz,noise_rms_hz=20000000.,qualification_cycles=128)
        assert disturbed['group_timing_ready'] and disturbed['pad_eye']['passes']
        assert not excessive['group_timing_ready'] and not excessive['pad_eye']['passes']
        launch=ForwardedLaneGroup(word_hz)
        reject(lambda:launch.arm([True,True,excessive['group_timing_ready']]))
        launch.arm([disturbed['group_timing_ready']]*3)
        launch.lose_reference(2)
        reject(lambda:launch.transfer(words,lane_skew_s=[0.]*3,word_delays=[0]*3))
        timing=forwarded_clock_budget(word_hz,reference_error_s=10e-12,
            pll_error_s=25e-12,distribution_skew_s=25e-12)
        assert timing['aligned']
        eye=pad_eye([0,1]*128,bit_rate=word_hz*10,capacitance_f=2e-12,
            sample_offset_ui=timing['sample_offset_ui'])
        assert eye['passes']
        switched=pad_eye([0,1]*128,bit_rate=word_hz*10,capacitance_f=2e-12,
            sample_offset_ui=timing['sample_offset_ui'],switch_tau_s=100e-12)
        assert switched['passes'] and switched['minimum_signed_eye_v']<eye['minimum_signed_eye_v']
        assert not pad_eye([0,1]*128,bit_rate=word_hz*10,capacitance_f=2e-12,
            sample_offset_ui=timing['sample_offset_ui'],switch_tau_s=1e-9)['passes']
        # Independent repeated-pole step response checks the coincident-pole branch.
        single=pad_eye([1],bit_rate=word_hz*10,capacitance_f=2e-12,switch_tau_s=100e-12)
        normalized_time=.5/(word_hz*10*100e-12)
        expected=.4*(1-(1+normalized_time)*math.exp(-normalized_time))
        assert abs(single['minimum_signed_eye_v']-expected)<1e-12
        assert not pad_eye([0,1]*128,bit_rate=word_hz*10,capacitance_f=30e-12)['passes']
        assert not forwarded_clock_budget(word_hz,reference_error_s=0,
            pll_error_s=0,distribution_skew_s=0,word_phase_error=1)['aligned']
        streams=[continuous_framed_lane(word_hz,host_rate,host_mode,phase_ui=phase,
            rate_error_ppm=ppm) for phase in (0.,.49,.99) for ppm in (-100.,0.,100.)]
        assert all(x['fault'] is None for x in streams)
        trace=continuous_framed_lane(word_hz,host_rate,host_mode,capture=True)
        captures=[[(t+delay/word_hz,w) for t,w in trace['captures']] for delay in (0,2,1)]
        causal=ForwardedLaneGroup(word_hz);causal.arm([True]*3)
        aligned_stream=causal.align_captures(captures,epoch=causal.epoch)
        assert aligned_stream['fault'] is None
        expected=np.arange(trace['consumed'])%1024
        assert np.array_equal(aligned_stream['words'],np.repeat(expected[:,None],3,axis=1))
        continuous_deskew=dict(rows=len(expected),frames=256,
            maximum_occupancy=aligned_stream['maximum_occupancy'],depth=4,
            source='actual codec/FIFO consumer events; common nominal lane frequency',
            pll_pad_applied_to_whole_stream=False)
        # Independent RX host clocks and frame service histories, not copies
        # of one lane trace. Align only the complete common word prefix; expose
        # finite-window tails separately rather than pretending they disappeared.
        host_returns=[continuous_framed_lane(word_hz,host_rate,host_mode,
            direction='rx',capture=True,host_error_ppm=ppm,host_phase_ui=phase,
            service_pause_frames=lane)
            for lane,(ppm,phase) in enumerate(((-100.,.1),(0.,.5),(100.,.9)))]
        assert all(r['fault'] is None for r in host_returns)
        common=min(len(r['captures']) for r in host_returns)
        captures=[r['captures'][:common] for r in host_returns]
        host_group=ForwardedLaneGroup(word_hz);host_group.arm([True]*3)
        too_small=host_group.align_captures(captures,epoch=host_group.epoch,depth=4)
        assert too_small['fault']=='overflow'
        host_group.arm([True]*3)
        returned=host_group.align_captures(captures,epoch=host_group.epoch,depth=128)
        assert returned['fault'] is None
        assert np.array_equal(returned['words'],np.repeat((np.arange(common)%1024)[:,None],3,axis=1))
        host_return_deskew=dict(rows=common,frames=256,depth=128,
            maximum_occupancy=returned['maximum_occupancy'],four_word_depth_overflows=True,
            trailing_captured_words=[len(r['captures'])-common for r in host_returns],
            lanes=[{k:v for k,v in r.items() if k!='captures'} for r in host_returns],
            scope='Independent framed RX host clocks, +/-100 ppm, 0/1/2-frame startup pauses; known first-word epoch; ideal CDC')
        receive_streams=[continuous_framed_lane(word_hz,host_rate,host_mode,
            direction='rx',phase_ui=phase,rate_error_ppm=ppm)
            for phase in (0.,.49,.99) for ppm in (-100.,0.,100.)]
        assert all(x['fault'] is None and x['consumed']>0 and
            x['produced']==x['consumed']+x['pending_words'] for x in receive_streams)
        assert continuous_framed_lane(word_hz,host_rate,host_mode,
            direction='rx',depth=4)['fault']=='overflow'
        assert continuous_framed_lane(word_hz,host_rate,host_mode,
            direction='rx',service_pause_frames=8)['fault']=='overflow'
        recovery=continuous_framed_lane(word_hz,host_rate,host_mode,
            direction='rx',service_pause_frames=1)
        assert recovery['fault'] is None and recovery['consumed']>0
        feedback_streams=[]
        for ppm in (-10000.,10000.):
            uncontrolled=continuous_framed_lane(word_hz,host_rate,host_mode,
                frames=512,rate_error_ppm=ppm)
            controlled=continuous_framed_lane(word_hz,host_rate,host_mode,
                frames=512,rate_error_ppm=ppm,feedback_delay_frames=2)
            assert uncontrolled['fault']==('overflow' if ppm<0 else 'underflow')
            assert controlled['fault'] is None and controlled['frames_completed']==512
            feedback_streams.append(controlled)
        assert continuous_framed_lane(word_hz,host_rate,host_mode,prefill=0)['fault']=='underflow'
        assert continuous_framed_lane(word_hz,host_rate,host_mode,
            rate_error_ppm=100000.)['fault']=='underflow'
        assert continuous_framed_lane(word_hz,host_rate,host_mode,
            rate_error_ppm=-100000.)['fault']=='overflow'
        rows.append(dict(pixel_clock_hz=word_hz,line_rate_bps=word_hz*10,chip_instances=3,
            pll_acquisition=acquisition,pll_refined=refined,pll_tuning_failure=failed,
            disturbed_pll_pad=disturbed,excessive_noise=excessive,
            canonical_resource_epoch_invalidation=True,canonical_forwarded_pll_construction=True,
            canonical_forwarded_receiver_words=len(received),
            canonical_pad_pins=pins,steady_pad_power=dc,canonical_power_ownership=power_accounting,
            transient_pad_energy=current_sink_energy_check(10*word_hz),
            external_return_rail_change_v=rail_change,external_return_energy_residuals_j=energy_residuals,
            independent_forwarded_payload=independent,independent_skew_failure=slipped,
            causal_pad_deskew=causal_pad,continuous_deskew=continuous_deskew,
            host_return_deskew=host_return_deskew,
            pad_eye=eye,finite_switch_pad=switched,forwarded_timing=timing,continuous_fifo=streams,
            receive_fifo=receive_streams,receive_pause_recovery=recovery,
            delayed_feedback_fifo=feedback_streams,
            framed_word_capacity_hz=capacity,required_word_rate_hz=word_hz,
            word_errors=0,excess_fractional_skew_rejected_by_errors=True,loss_cancels_group=True))
    levels=current_sink_levels();assert abs(levels['low_v']-2.9)<1e-12
    assert abs(levels['source_power_w']-levels['sink_power_w']-levels['termination_power_w'])<1e-15
    return dict(cases=rows,electrical_hypothesis=levels,full_chip_closure=False,
        limitations=['External forwarded clock, deskew and readiness are prescribed; no multi-die PLL/CDC qualification.',
            'Opaque TMDS symbols only; full video timing/encoding, HDMI packets/audio and protocol compliance remain external/unverified.',
            'DC current-sink circuit, common-mode tolerance, ESD, clock input bandwidth and lane skew require schematic proof.'])


def forwarded_canonical_lifecycle(direction='rx'):
    import time
    from stream_codec import encode
    if direction not in ('rx','tx'):raise ValueError('Simplex direction required')
    began=time.monotonic()
    c=make_chip()
    c.configure_resources(engine='wire',line_rate_bps=1.485e9,
        tx_enabled=direction=='tx',rx_enabled=direction=='rx')
    c.execute_management('configure_wire_interface',3,c.time)
    c.configure(1,c.time);c.advance(2e-6)
    assert c.state=='active' and c.wire_pll.locked and not c.rf_pll.powered
    words=[(37*i+19)%1024 for i in range(8 if direction=='rx' else 4)]
    if direction=='rx':
        c.incoming_wire(words,c.time+10e-9,phase=0.,ppm=0.)
        c.start_wire_return(c.time+75e-9);c.advance(2.14e-6)
        assert c.host_wire==words and c.rx_accepted==c.rx_staged==8
        accounting=dict(received_words=c.rx_accepted,host_words=c.host_wire)
    else:
        origin=c.time
        for i,word in enumerate(encode(1,words,[],0)):
            c.feed(word,c.epoch,origin+(i+1)/312.5e6)
        assert list(c.wire_queue)==words
        c.schedule_wire(len(words),c.time+10e-9);c.advance(c.time+50e-9)
        assert c.wired_output==words
        accounting=c.wire_accounting()
        assert accounting['underflows']==0 and accounting['pending']==0
        assert c.wired_power_accounting()['external_return_current_a']>.0079
    assert c.time==c.analog_owner.time==c.wire_pll.time==c.rf_pll.time
    c.set_reference(False,c.time)
    assert c.state=='draining'
    if direction=='rx':assert not c.live_rx.enabled
    else:
        assert not c.serializer.active and c.serializer.drive==0.
        c.advance(c.time+1e-9)
        assert c.wired_power_accounting()['external_return_current_a']<1e-6
    stopped_epoch=c.epoch
    reject(lambda:c.configure_resources(engine='rf'))
    reject(lambda:c.acknowledge_drain(stopped_epoch,c.time))
    c.acknowledge_host_abort(stopped_epoch,c.time)
    c.acknowledge_drain(stopped_epoch,c.time)
    assert c.state=='reset' and c.epoch==stopped_epoch+1
    held_pad=c.channel
    state_before=(held_pad.state,held_pad.current_state,held_pad.tail_state,held_pad.common_drop_state)
    c.configure_resources(engine='rf')
    assert c.channel is held_pad
    assert state_before==(held_pad.state,held_pad.current_state,held_pad.tail_state,held_pad.common_drop_state)
    assert c.active_engine=='rf' and not c.wire_pll.powered and c.rf_pll.powered
    assert c.wire_interface['clock_source']=='embedded' and not c.clocks_ready()
    retained=c.retired_dc_pad(c.time)
    assert retained is not None
    assert abs(retained.tail_state-held_pad.tail_state)<1e-12
    c.configure_analog_loads()
    residue_now=c.analog_owner.external_return_current(c.time)
    residue_later=c.analog_owner.external_return_current(c.time+100e-12)
    assert abs(residue_now-retained.tail_current_a*retained.tail_state)<1e-15
    if direction=='tx':assert 0<residue_later<residue_now
    reject(lambda:c.schedule_wire(1,c.time+1e-9))
    reject(lambda:c.incoming_wire([1],c.time+1e-9))
    expected=c.retired_dc_pad(c.time)
    c.configure_resources(engine='wire',line_rate_bps=1.485e9,
        tx_enabled=direction=='tx',rx_enabled=direction=='rx')
    c.execute_management('configure_wire_interface',3,c.time)
    c.configure(1,c.time)
    assert c.dc_pad_residue is None
    for field in ('state','current_state','tail_state','common_drop_state'):
        assert abs(getattr(c.channel,field)-getattr(expected,field))<1e-12
    assert c.state=='acquiring' and not c.reference
    return dict(model_id=c.model_id,direction=direction,line_rate_bps=1.485e9,acquired_at_s=2e-6,
        accounting=accounting,reference_loss_drains=True,drain_acknowledged=True,
        rf_resource_handover=True,rf_payload_acquired=False,retained_return_current_a=residue_now,
        retained_return_after_100ps_a=residue_later,dc_reconstruction_preserves_state=True,end_time_s=c.time,
        elapsed_s=time.monotonic()-began,scope='Canonical coupled finite host/PHY window',
        limitations=['Direct configuration; no serialized startup commands.',
            'RX prescribed external word alignment/source timing; TX uses internal serializer observer.',
            'Only 1080p lane rate, finite words; no sustained three-chip link.',
            'RF handover checks resource/epoch guards and retained pad state, not acquired RF payload or handover energy.',
            'RX termination supply/physical host capture and receiver common-mode qualification remain open.'])


def main():
    if not __debug__:raise RuntimeError('Assertions must remain enabled')
    ap=argparse.ArgumentParser();ap.add_argument('--coupled',action='store_true');ap.add_argument('--rf-pll-projection',action='store_true');ap.add_argument('--rf-startup-solvers',action='store_true');ap.add_argument('--forwarded-lifecycle',action='store_true');ap.add_argument('--forwarded-direction',choices=('rx','tx'),default='rx');args=ap.parse_args()
    files=list((P/'system_model/connected').glob('*.py'))+list((P/'system_model/architecture_fast').glob('*.py'))
    files += [P/'verification'/n for n in ('protocol_model_check.py','full_chip_model.py','check_contract.py',
              'fast_exclusive_engine.py','fast_loaded_output.py','host_bank_supply.py','stream_codec.py','transport_model.py')]+[P/'spec/contract.json']
    hashes={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    report=dict(status='running',model_id=parameters()['model_id'],source_sha256=hashes,
        full_chip_closure=False,protocol_compliance=False,checks={},
        remaining=['Complete packet waveforms and independent packet/PER observers.',
        'Full canonical acquisition, long-packet RX/TX, spectral masks and phase-noise envelopes.',
        'HE20 synthetic-training equalization and fine CFO recovery are tested on held-out symbols; real preamble/coarse acquisition, sample timing recovery and 8-bit quality remain open.',
        'USB negotiation, HS burst recovery, timed pad packet adapter, canonical active short-frame traffic and RTL integration.',
        'Serial causal RX passes test-link framing at all five profile rates; SATA OOB-to-data, DP training/AUX/SSC, PCIe training and Ethernet/SGMII PCS peer operation remain open.',
        'Disabled USB capacitance in the serial RX channel, package/ESD and transistor qualification.',
        'Warm-hop readiness and calibration validity across process/voltage/temperature.'])
    output=P/'evidence'/('protocol-rf-startup-solvers.json' if args.rf_startup_solvers else 'protocol-rf-pll-projection.json' if args.rf_pll_projection else ('protocol-forwarded-tx-lifecycle.json' if args.forwarded_direction=='tx' else 'protocol-forwarded-lifecycle.json') if args.forwarded_lifecycle else 'protocol-model-coupled.json' if args.coupled else 'protocol-model.json')
    def save():output.write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        checks=[("rf_startup_solvers",rf_startup_solver_checks)] if args.rf_startup_solvers else [("acquired_rf_projection",acquired_rf_projection_checks)] if args.rf_pll_projection else [("forwarded_canonical_lifecycle",lambda:forwarded_canonical_lifecycle(args.forwarded_direction))] if args.forwarded_lifecycle else [('generic_configuration',generic_configuration_checks),('multi_chip_video',multi_chip_video_checks),('rf_symbols',waveform_checks),('rf_link_quality',link_quality_checks),('rf_conversion_impairments',rf_conversion_impairment_checks),('clocked_rf_conversion',clocked_rf_conversion_checks),('chirp_frequency',chirp_frequency_checks),('chirp_training',chirp_training_checks),('chirp_drift',chirp_drift_checks),('trained_receiver',trained_receiver_checks),('carrier_recovery',carrier_recovery_checks),('line_timing',line_and_timing_checks),('short_burst_clock',short_burst_clock_checks),('pad_burst_clock',pad_burst_clock_checks),('usb_transport_reuse',usb_reuse_checks),('short_frame_lifecycle',short_frame_lifecycle_checks),('serial_rates',serial_checks),('serial_receive',serial_receive_checks),('oob_observation',oob_observation_checks),('sata_startup',sata_startup_checks)]+([('canonical_coupling',coupled_checks)] if args.coupled else [])
        for name,fn in checks:
            report['checks'][name]=fn();save();print(name,'passed',flush=True)
        if not args.forwarded_lifecycle and not args.rf_pll_projection and not args.rf_startup_solvers:report['rf_link_quality_closed']=all(r['quality_status']=='finite_fixture_pass' for r in report['checks']['rf_link_quality'])
        assert all(hashlib.sha256((P/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
        report['status']='passed'
    except BaseException as e:report.update(status='failed',error=repr(e));raise
    finally:save()


if __name__=='__main__':main()
