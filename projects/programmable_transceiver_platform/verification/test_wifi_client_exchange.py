"""Shared-design exchange tests plus explicit normalized RF/codec fixtures.

Bare SharedRFPath examples supply independent physical hypotheses. ClientBench
uses a shared snapshot with recorded simplified rail, phase and TX assumptions.
"""
import unittest
import numpy as np
from wifi_client_exchange import run,ClientBench,FS

TEST_DESIGN_ROLES = {
    'ClientExchangeTests': ('shared_design', 'ClientBench/run use the shared snapshot; peer signals, calibration records and prescribed RF impairments isolate protocol/transport behavior.'),
    'ClientExchangeTests.test_effective_dac_noise_is_retained_in_held_history': ('independent_fixture', 'Bare normalized RF path with independently assigned DAC noise.'),
    'ClientExchangeTests.test_pa_is_fixed_across_tx_and_idle_filter_tail': ('independent_fixture', 'Bare RF paths with assigned compression, checked against the independent PA transfer.'),
    'ClientExchangeTests.test_additive_converter_phase_uses_converter_carrier': ('independent_fixture', 'Assigned phase tone checked against its crossing equation.'),
    'ClientExchangeTests.test_rate_converter_preserves_outer_tones': ('independent_fixture', 'Analytical complex sinusoids test resampling.'),
    'ClientExchangeTests.test_resampler_validity_covers_every_contaminated_output': ('independent_fixture', 'Impulse contamination and independent resampling identify affected samples.'),
    'ClientExchangeTests.test_gain_command_settling_and_status_share_native_timeline': ('independent_fixture', 'Bare RF path with assigned command timing and response constants.'),
    'ClientExchangeTests.test_pga_transition_is_continuous_and_preserves_history': ('independent_fixture', 'Assigned first-order gain transitions and retained mathematical history.'),
    'ClientExchangeTests.test_pga_ready_depends_on_step_direction_and_error_bound': ('independent_fixture', 'Independent gain-step error equation under assigned response constants.'),
    'ClientExchangeTests.test_tx_leakage_leaves_rx_filter_history_after_direction_change': ('independent_fixture', 'Assigned leakage in bare normalized filter paths.'),
    'SharedDesignTests': ('shared_design', 'Snapshot/configuration propagation, identity isolation and explicit hypothetical receiver allocations.'),
}

def queue_limit(design):
    queues=design.contract['transport']['scheduling']
    return min(queues['ingress_bits_per_source'],queues['egress_bits_per_source'])

class ClientExchangeTests(unittest.TestCase):
    def test_expiring_calibration_blocks_actual_tx_before_queue_or_launch(self):
        from dataclasses import replace
        from rf_power_calibration import CalibrationValidity,IQCalibration
        b=ClientBench();payload=bytes(range(64))
        b.receive_intent('request',payload)
        # Synthetic external characterization, not a chip sensor or measured die.
        operating=dict(temperature_c=(25.,26.),supplies_v={'VDD':(3.28,3.32)})
        def record(context,age):
            return CalibrationValidity(context,(24.,27.),{'VDD':(3.25,3.35)},0.,age)
        b.tx_iq_calibration=IQCalibration(b.tx_iq_context,1.,.003,0.,0.,record(b.tx_iq_context,1.))
        b.tx_timing_validity=record(b.tx_timing_context,1.)
        before=(b.chip.time,len(b.host_tx),b.tx_open)
        with self.assertRaisesRegex(ValueError,'Operating measurements'):
            b.transmit_intent('missing qualification',payload)
        self.assertEqual((b.chip.time,len(b.host_tx),b.tx_open),before)
        b.calibration_operating=operating
        # Valid at command admission, but expires before the waveform completes.
        b.tx_timing_validity=record(b.tx_timing_context,b.chip.time+20e-6)
        with self.assertRaisesRegex(ValueError,'expired'):
            b.transmit_intent('expires during response',payload)
        self.assertEqual((b.chip.time,len(b.host_tx),b.tx_open),before)
        b.tx_timing_validity=replace(b.tx_timing_validity,maximum_age_s=1.)
        original=b.rf.tx_cutoff_hz;b.rf.tx_cutoff_hz=10e6
        with self.assertRaisesRegex(ValueError,'identity'):
            b.transmit_intent('changed filter',payload)
        self.assertEqual((b.chip.time,len(b.host_tx),b.tx_open),before)
        b.rf.tx_cutoff_hz=original
        b.transmit_intent('explicitly requalified response',payload)
        self.assertTrue(b.rows[-1]['crc_ok'])
        self.assertTrue(b.rows[-1]['calibration_validity_enforced'])

    def test_effective_dac_noise_is_retained_in_held_history(self):
        from wifi_client_exchange import SharedRFPath
        # Zero codes isolate excess converter noise from quantization and signal.
        ideal=SharedRFPath(); noisy=SharedRFPath(); noisy.dac_enob=9.
        codes=np.zeros(2048,complex)
        drive=np.zeros(int(np.ceil(len(codes)*80e6/FS)),complex)
        ideal.process(drive,'tx',held_values=codes)
        noisy.process(drive,'tx',held_values=codes)
        self.assertTrue(np.all(np.asarray(ideal.tx_values)==0))
        stored=np.asarray(noisy.tx_values[1:-1])
        # Undo the separately modeled I/Q image to inspect DAC code noise.
        real=stored.real/1.003; imag=stored.imag/.997
        expected=((2/2**9)**2-(1/512)**2)/12
        self.assertAlmostEqual(np.var(real)/expected,1.,delta=.12)
        self.assertAlmostEqual(np.var(imag)/expected,1.,delta=.12)
        history=list(noisy.tx_values)
        noisy.process(np.zeros(80,complex),'idle')
        self.assertEqual(noisy.tx_values,history)

    def test_pa_is_fixed_across_tx_and_idle_filter_tail(self):
        from wifi_client_exchange import SharedRFPath
        from rf_power_calibration import pa_compression
        plain=SharedRFPath(); compressed=SharedRFPath()
        compressed.pa_input_p1db_envelope=.1
        codes=np.full(40,.3+.2j)
        # Equal seeds make additive output noise identical in both paths.
        drive=np.zeros(80,complex)
        baseline=plain.process(drive,'tx',held_values=codes)
        actual=compressed.process(drive,'tx',held_values=codes)
        self.assertLess(np.linalg.norm(actual),np.linalg.norm(baseline))
        tail=plain.process(np.zeros(80,complex),'idle')
        compressed_tail=compressed.process(np.zeros(80,complex),'idle')
        np.testing.assert_allclose(compressed_tail,
            pa_compression(tail,input_p1db_envelope=.1))
        self.assertEqual(compressed.pa_input_p1db_envelope,.1)

    def test_retained_lifecycle_and_finite_queues(self):
        from design_definition import load_design
        design=load_design();result=run(design=design)
        self.assertTrue(result['completed']);self.assertEqual(result['epoch'],0)
        self.assertEqual(len(result['rows']),13)
        for row in result['rows']:
            self.assertTrue(row['crc_ok'])
            self.assertLessEqual(row['queue_high_bits'],queue_limit(design))
            if row['direction']=='tx':self.assertLessEqual(abs(row['response_gap_s']-10e-6),.5/FS+1e-15)
        self.assertFalse(result['physical_qualification'])

    def test_unwhitened_padding_overload_is_rejected_before_queue_mutation(self):
        b=ClientBench(pga_gain_db=24);b.mcs=0;b.data_whitening_seed=None
        payload=bytes(range(128))
        before=(b.chip.time,len(b.host_tx),b.tx_open)
        with self.assertRaisesRegex(ValueError,'DAC peak allowance'):
            b.transmit_intent('unwhitened_padding_control',payload,amplitude=.12)
        self.assertEqual((b.chip.time,len(b.host_tx),b.tx_open),before)

    def test_selected_tx_filter_prices_fir_delay_and_preserves_queues(self):
        payload=bytes(range(128))
        for mcs in range(8):
            with self.subTest(mcs=mcs):
                # TX timing fixture: reduce RX clipping with an explicit legal gain.
                b=ClientBench(pga_gain_db=24);b.mcs=mcs
                self.assertTrue(b.tx_preparation_record()['uses_selected_correction'])
                self.assertEqual(b.rf.dac_enob,b.design.architecture['model_assumptions']['paired_dac']['parameters']['enob'])
                b.receive_intent('request',payload)
                pending=len(b.host_tx)
                with self.assertRaisesRegex(ValueError,'Late response'):
                    b.transmit_intent('late',payload,decision_s=7e-6,amplitude=.12)
                self.assertEqual(len(b.host_tx),pending)
                b.transmit_intent('response',payload,amplitude=.12)
                row=b.rows[-1]
                self.assertTrue(row['crc_ok'])
                self.assertLessEqual(row['queue_high_bits'],queue_limit(b.design))
                self.assertAlmostEqual(row['waveform_delay_s'],24/FS)
                self.assertLessEqual(abs(row['response_gap_s']-10e-6),.5/FS)
                self.assertAlmostEqual(row['response_gap_s']-row['dac_launch_gap_s'],.4e-6+24/FS)
                self.assertGreater(row['precursor_energy_fraction'],0.)

    def test_antenna_delay_uncertainty_is_admitted_before_queue_mutation(self):
        b=ClientBench();payload=bytes(range(64))
        b.receive_intent('request',payload)
        b.tx_delay_bounds=(.3e-6,.5e-6)
        pending=len(b.host_tx)
        with self.assertRaisesRegex(ValueError,'timing uncertainty'):
            b.transmit_intent('too precise',payload)
        self.assertEqual(len(b.host_tx),pending)
        b.transmit_intent('bounded',payload,timing_tolerance_s=120e-9)
        low,high=b.rows[-1]['response_gap_bounds_s']
        self.assertGreaterEqual(low,10e-6-120e-9)
        self.assertLessEqual(high,10e-6+120e-9)
        self.assertAlmostEqual(high-low,200e-9)

    def test_iq_calibration_runs_before_dac_admission(self):
        from rf_power_calibration import IQCalibration
        b=ClientBench();payload=bytes(range(64))
        b.receive_intent('request',payload)
        # An impossible gain correction must fail before committing host data.
        b.tx_iq_calibration=IQCalibration(b.tx_iq_context,.001,0.,0.,0.)
        pending=len(b.host_tx)
        with self.assertRaisesRegex(ValueError,'DAC peak'):
            b.transmit_intent('overdriven correction',payload)
        self.assertEqual(len(b.host_tx),pending)
        # Known flat image coefficient of this behavioral path, not silicon data.
        b.tx_iq_calibration=IQCalibration(b.tx_iq_context,1.,.003,0.,0.)
        b.transmit_intent('corrected response',payload)
        self.assertTrue(b.rows[-1]['crc_ok'])

    def test_converter_clock_uses_lo_time_error_not_divided_carrier_error(self):
        from wifi_client_exchange import SharedRFPath
        from oscillator_noise import PhaseNoise
        path=SharedRFPath();path.shared_converter_clock=True
        path.phase_noise=PhaseNoise(((100e3,.04,.3),))
        ideal=np.arange(1000)/FS
        error=path.clock_error(ideal)
        complete=path.phase_noise.plus(PhaseNoise(((31.25e6,.002,-np.pi/2),)))
        self.assertLess(np.max(abs(2*np.pi*2412e6*error+complete.phase(ideal+error))),1e-12)
        self.assertLess(np.max(abs(error)),3e-12)
        self.assertGreater(np.min(np.diff(ideal+error)),0.)
        record=path.clock_configuration()
        actual=ideal+error
        direct=sum(amplitude*np.cos(2*np.pi*frequency*actual+phase)
                   for frequency,amplitude,phase in record['converter_phase_tones'])
        self.assertLess(np.max(abs(2*np.pi*record['converter_hz']*error+direct)),1e-12)
        bench=ClientBench();bench.rf.shared_converter_clock=True
        bench.rf.phase_noise=path.phase_noise
        context=bench.context_record()
        saved=context['rf_fixture_parameters']['clock_configuration']
        self.assertEqual(saved,record)
        saved['lo_phase_tones'][0][1]=100.
        saved['converter_phase_tones'].clear()
        self.assertEqual(bench.rf.clock_configuration(),record)


    def test_additive_converter_phase_uses_converter_carrier(self):
        from wifi_client_exchange import SharedRFPath
        from oscillator_noise import PhaseNoise
        path=SharedRFPath()
        peak_s=20e-12
        path.converter_phase_noise=PhaseNoise(((611e3,2*np.pi*FS*peak_s,.3),))
        ideal=np.arange(1000)/FS
        error=path.clock_error(ideal)
        self.assertLess(np.max(abs(2*np.pi*FS*error+
            path.converter_phase_noise.phase(ideal+error))),1e-12)
        self.assertGreater(np.max(abs(error)),.99*peak_s)
        self.assertLessEqual(np.max(abs(error)),peak_s)
        self.assertGreater(np.min(np.diff(ideal+error)),0.)

    def test_received_pilot_update_drives_response_without_phase_truth(self):
        from oscillator_noise import PhaseNoise
        b=ClientBench();b.track_rx_pilot_cfo=True;b.rf.shared_converter_clock=True
        b.rf.phase_noise=PhaseNoise.from_ssb(colored_at_100khz_dbc_hz=-105.,
            floor_dbc_hz=-150.,bins=48,seed=947)
        payload=np.random.default_rng(917).integers(0,256,1024,dtype=np.uint8).tobytes()
        b.receive_intent('tracked request',payload)
        self.assertNotEqual(b.measured_cfo_hz,b.rows[-1]['preamble_cfo_hz'])
        b.transmit_intent('tracked response',payload,amplitude=.08)
        self.assertTrue(b.rows[-1]['crc_ok'])
        self.assertIsNotNone(b.rows[-1]['peer_pilot_cfo_hz'])
        self.assertLessEqual(b.rows[-1]['queue_high_bits'],queue_limit(b.design))

    def test_late_fpga_decision_cannot_be_hidden_by_prefill(self):
        b=ClientBench();payload=np.random.default_rng(500).integers(0,256,64,dtype=np.uint8).tobytes()
        b.receive_intent('request',payload)
        with self.assertRaisesRegex(ValueError,'Late response'):
            b.transmit_intent('response',payload,decision_s=9e-6)
        self.assertEqual(b.chip.rf_launch_events,[])
        self.assertFalse(b.chip.rf_launch.output)

    def test_frequency_correction_from_received_training(self):
        # Independent peer offsets exercise both correction signs. Truth is used
        # only for scoring: the TX NCO receives the acquired preamble estimate.
        payload=np.random.default_rng(712).integers(0,256,256,dtype=np.uint8).tobytes()
        for offset in (-90000.,-43000.,0.,43000.,90000.):
            with self.subTest(peer_offset_hz=offset):
                b=ClientBench();b.peer_offset_hz=offset
                b.receive_intent('trigger_training',payload)
                b.transmit_intent('response_data',payload)
                self.assertLess(abs(b.rows[-1]['residual_cfo_hz']),350.)
                self.assertTrue(b.rows[-1]['crc_ok'])
                self.assertEqual(b.chip.epoch,0)

    def test_calibrated_amplitude_reaches_actual_dac_path(self):
        from rf_power_calibration import PowerCalibration
        table=PowerCalibration(('synthetic_board',),((.06,-14.),(.12,-8.)),.7)
        payload=np.random.default_rng(90).integers(0,256,256,dtype=np.uint8).tobytes()
        outputs=[]
        for power in (-14.,-8.):
            b=ClientBench();b.receive_intent('request',payload)
            scale=table.amplitude(power,context=table.context,maximum_dbm=-7.)
            b.transmit_intent('response',payload,amplitude=scale)
            outputs.append(b.rows[-1]['output_mean_square'])
        # Confirm measured waveform energy changes through queues, quantization,
        # reconstruction and analog impairments, not merely a bookkeeping field.
        self.assertAlmostEqual(10*np.log10(outputs[1]/outputs[0]),6.02,delta=.15)

    def test_rejected_waveform_does_not_contaminate_next_response(self):
        b=ClientBench();payload=bytes(range(128))
        b.receive_intent('request',payload)
        initial_words=len(b.host_tx)
        for options,error in [({'amplitude':3.},'peak allowance'),
                              ({'decision_s':9e-6},'Late response')]:
            with self.assertRaisesRegex(ValueError,error):
                b.transmit_intent('invalid',payload,**options)
            self.assertEqual(len(b.host_tx),initial_words)
            self.assertEqual(b.chip.rf_launch_events,[])
        b.transmit_intent('valid',payload)
        self.assertTrue(b.rows[-1]['crc_ok'])

    def test_external_rx_calibration_drives_uplink_request(self):
        from rf_power_calibration import ReceivePowerCalibration,PowerCalibration,requested_uplink_power
        payload=bytes(range(128))
        reference=ClientBench();reference.receive_intent('equipment_reference',payload)
        table=ReceivePowerCalibration(('2412MHz','fixed_gain','selected_filter'),
            -50.,reference.measured_ltf_power,(-65.,-40.),.5)
        for wanted in (-56.,-53.,-47.):
            b=ClientBench();b.rf.wanted_dbm=wanted
            b.receive_intent('peer_trigger',payload)
            measured=table.estimate(b.measured_ltf_power,context=table.context)
            self.assertAlmostEqual(measured,wanted,delta=.5)
            requested=requested_uplink_power(15.,measured,-75.)
            self.assertAlmostEqual(requested,15.-wanted-75.,delta=.5)
            tx_table=PowerCalibration(('synthetic_equipment',),
                ((.03,-20.),(.06,-14.),(.12,-8.),(.24,-2.)),.7)
            amplitude=tx_table.amplitude(requested,context=tx_table.context,maximum_dbm=-1.)
            b.transmit_intent('power_adjusted_response',payload,amplitude=amplitude)
            self.assertTrue(b.rows[-1]['crc_ok'])
            self.assertEqual(b.chip.epoch,0)


    def test_all_advertised_mcs_data_paths(self):
        payload=np.random.default_rng(122).integers(0,256,256,dtype=np.uint8).tobytes()
        for mcs in range(8):
            with self.subTest(mcs=mcs):
                b=ClientBench();b.mcs=mcs
                b.receive_intent('mcs_receive',payload)
                b.transmit_intent('mcs_reply',payload)
                self.assertTrue(all(row['crc_ok'] for row in b.rows))
                target=b.design.architecture['rf_interoperability']['tx_error_allocation']['design_target_db']
                self.assertLessEqual(b.rows[-1]['scalar_observer_evm'],10**(target/20))
                self.assertEqual(b.chip.epoch,0)

    def test_common_reference_rate_error_has_explicit_latency(self):
        payload=bytes(range(256))*16
        for offset in (-90000.,90000.):
            with self.subTest(offset=offset):
                b=ClientBench();b.couple_peer_clocks=True;b.peer_offset_hz=offset
                b.receive_intent('long_rate_offset_packet',payload)
                self.assertTrue(b.rows[-1]['crc_ok'])
                b.transmit_intent('priced_native_rate_conversion',payload)
                self.assertTrue(b.rows[-1]['crc_ok'])
                self.assertLessEqual(abs(b.rows[-1]['response_gap_s']-10e-6),.5/FS+1e-15)

    def test_rate_converter_preserves_outer_tones(self):
        from wifi_client_exchange import clock_warp
        n=np.arange(16384)
        for f in (1e6,5e6,9.53125e6):
            for ratio in (1-90000/2412e6,1+90000/2412e6):
                y=clock_warp(np.exp(2j*np.pi*f*n/FS),ratio,taps=129)
                truth=np.exp(2j*np.pi*f*np.arange(len(y))*ratio/FS)
                error=np.sqrt(np.mean(abs(y[64:-64]-truth[64:-64])**2))
                self.assertLess(error,.003)

    def test_training_gated_gain_feedback_uses_serialized_gap(self):
        from wifi_client_exchange import gain_feedback_case
        from design_definition import load_design
        from functools import partial
        selected=load_design()
        gain_feedback_case=partial(gain_feedback_case,design=selected)
        weak=gain_feedback_case(wanted_dbm=-65.,blocker_dbm=-40.)
        self.assertTrue(weak['decoded'])
        self.assertEqual(weak['adc_clipped_pairs'],0)
        self.assertEqual(len(weak['decision']),1)
        self.assertEqual(weak['decision'][0]['target_db'],42)
        self.assertEqual(sum(g['count'] for g in weak['gaps']),weak['invalid_native_pairs'])
        self.assertLessEqual(weak['queue_high_bits'],queue_limit(selected))
        strong=gain_feedback_case(wanted_dbm=-50.,blocker_dbm=-40.)
        self.assertTrue(strong['decoded'])
        self.assertEqual(strong['adc_clipped_pairs'],0)
        self.assertEqual(strong['decision'][0]['target_db'],27)
        self.assertTrue(weak['gain_settled_before_ltf'])
        for offset in (-90000.,90000.):
            delayed=gain_feedback_case(start_sample=219,carrier_offset_hz=offset)
            self.assertTrue(delayed['decoded'])
            self.assertTrue(delayed['gain_settled_before_ltf'])
        blocker=gain_feedback_case(transmit=False,blocker_dbm=-40.)
        self.assertFalse(blocker['decoded'])
        self.assertEqual(blocker['decision'],[])

    def test_resampler_validity_covers_every_contaminated_output(self):
        from scipy.signal import resample_poly
        from wifi_client_exchange import resample_poly_validity
        for up,down in ((320,603),(603,320),(1,1)):
            valid=np.ones(513,bool);valid[0]=valid[247]=valid[-1]=False
            changed=resample_poly((~valid).astype(float),up,down)
            accepted=resample_poly_validity(valid,up,down)
            self.assertEqual(len(accepted),len(changed))
            self.assertLess(np.max(abs(changed[accepted])),1e-12)
            self.assertTrue(np.any(~accepted))

    def test_gain_invalid_samples_cannot_train_or_decode_data(self):
        from rf_gain_command import encode_gain
        from wideband_packet import acquire
        payload=bytes(range(128))
        from design_definition import load_design
        design=load_design().hypothetical(reason='Fast PGA isolates gain-invalid sample exclusion',changes={
            'blocks.pga_i.parameters.gain_response_tau_s':100e-9,
            'blocks.pga_q.parameters.gain_response_tau_s':100e-9})
        tau=design.architecture['blocks']['pga_i']['parameters']['gain_response_tau_s']
        b=ClientBench(design=design,pga_gain_db=27);b.rf.wanted_dbm=-65;b.rf.blocker_dbm=-40
        b.rf.schedule_gain_command(encode_gain(20,42,0),0,
                                   host_issue_s=4e-6,tau_s=tau)
        b.receive_intent('gain during acquisition',payload)
        from scipy.signal import resample_poly
        samples=resample_poly(b.last_native_rx,320,603)
        found,_=acquire(samples,valid=b.last_rx_valid)
        coarse,ltf=found['coarse_start_sample'],found['ltf_start_sample']
        self.assertTrue(np.all(b.last_rx_valid[coarse:coarse+111]))
        self.assertTrue(np.all(b.last_rx_valid[ltf:ltf+128]))
        denied,_=acquire(samples,valid=np.zeros(len(samples),bool))
        self.assertFalse(denied['legacy_training_acquired'])
        b=ClientBench(design=design,pga_gain_db=27)
        b.rf.schedule_gain_command(encode_gain(20,42,0),0,
                                   host_issue_s=30e-6,tau_s=tau)
        with self.assertRaisesRegex(ValueError,'Gain discontinuity'):
            b.receive_intent('gain inside payload',payload)
        self.assertEqual(b.rows,[])

    def test_gain_command_settling_and_status_share_native_timeline(self):
        from wifi_client_exchange import SharedRFPath
        from rf_gain_command import encode_gain,decode_gain
        for initial,target in ((27,42),(42,27)):
            path=SharedRFPath();path.pga_db=initial
            command=encode_gain(20,target,7)
            with self.assertRaisesRegex(ValueError,'completed sample snapshot'):
                path.schedule_gain_command(command,7,host_issue_s=2e-6,
                                           tau_s=100e-9,snapshot_complete=False)
            self.assertEqual(path.pga_updates,[])
            event=path.schedule_gain_command(command,7,host_issue_s=2e-6,tau_s=100e-9)
            status=decode_gain(event['status'],7,status=True)
            first,end=event['first_invalid_sample'],event['first_valid_sample']
            times=np.arange(first-1,end+2)/FS
            valid=path.gain_valid_at(times)
            self.assertEqual(np.count_nonzero(~valid),status['invalid_pairs'])
            self.assertTrue(valid[0]);self.assertTrue(valid[-1])
            self.assertFalse(valid[1]);self.assertTrue(valid[-2])
            gain=path.pga_gain_at(np.array([end/FS]))[0]
            self.assertLessEqual(abs(gain/10**(target/20)-1),.003)
            self.assertGreaterEqual(event['commit_s'],2e-6+event['transport_bound_s'])
            self.assertLess(event['commit_s'],2e-6+event['transport_bound_s']+1/FS)
            before=list(path.pga_updates);intervals=list(path.gain_invalid_intervals)
            with self.assertRaisesRegex(ValueError,'frame count'):
                path.schedule_gain_command(encode_gain(20,initial,8),8,
                                           host_issue_s=5e-6,tau_s=1e-6)
            bad=command.copy();bad[0]^=1
            with self.assertRaises(ValueError):
                path.schedule_gain_command(bad,7,host_issue_s=5e-6,tau_s=100e-9)
            self.assertEqual(path.pga_updates,before)
            self.assertEqual(path.gain_invalid_intervals,intervals)

    def test_pga_transition_is_continuous_and_preserves_history(self):
        from wifi_client_exchange import SharedRFPath
        path=SharedRFPath();path.pga_db=27.
        path.schedule_pga(42.,commit_s=1e-6,tau_s=100e-9)
        path.schedule_pga(30.,commit_s=1.2e-6,tau_s=100e-9)
        t=np.linspace(0,3e-6,301)
        whole=path.pga_gain_at(t)
        chunked=np.r_[path.pga_gain_at(t[:117]),path.pga_gain_at(t[117:])]
        np.testing.assert_array_equal(whole,chunked)
        self.assertAlmostEqual(path.pga_gain_at(np.array([1e-6]))[0],10**(27/20))
        before=path.pga_gain_at(np.array([1.2e-6-1e-15]))[0]
        after=path.pga_gain_at(np.array([1.2e-6]))[0]
        self.assertLess(abs(after-before),1e-6)
        self.assertLess(abs(whole[-1]-10**(30/20)),1e-5)
        with self.assertRaises(ValueError):path.schedule_pga(28.,commit_s=4e-6,tau_s=1e-7)

    def test_pga_ready_depends_on_step_direction_and_error_bound(self):
        from wifi_client_exchange import SharedRFPath
        for initial,target in ((27.,42.),(42.,27.)):
            path=SharedRFPath();path.pga_db=initial
            status=path.schedule_pga(target,commit_s=1e-6,tau_s=100e-9)
            final=10**(target/20)
            at=path.pga_gain_at(np.array([status['ready_s']]))[0]
            self.assertAlmostEqual(abs(at-final)/final,.003,places=12)
            self.assertGreater(status['settling_s'],400e-9)
            before=path.pga_gain_at(np.array([status['ready_s']-1e-9]))[0]
            self.assertGreater(abs(before-final)/final,.003)

    def test_tx_leakage_leaves_rx_filter_history_after_direction_change(self):
        from wifi_client_exchange import SharedRFPath
        outputs=[]
        for coupling in (0.,.1):
            path=SharedRFPath();path.pga_db=0.;path.blocker_dbm=None
            path.tx_to_rx_filter_coupling=coupling
            path.process(np.zeros(320,complex),'tx',held_values=np.full(150,.2+0j))
            outputs.append(path.process(np.zeros(400,complex),'rx'))
        residue=outputs[1]-outputs[0]
        self.assertGreater(max(abs(residue[:40])),.005)
        self.assertLess(max(abs(residue[-40:])),max(abs(residue[:40]))/100)

class SharedDesignTests(unittest.TestCase):
    def test_selected_fpga_preparation_and_dac_noise_follow_snapshot(self):
        from copy import deepcopy
        from design_definition import load_design,DesignDefinition
        d=load_design();a=d.architecture;c=d.contract
        a['rf_interoperability']['fpga_tx_preparation'].update(taps=65,coefficient_fraction_bits=14)
        a['model_assumptions']['paired_dac']['parameters']['enob']=9.
        variant=DesignDefinition.from_documents(c,a)
        b=ClientBench(design=variant);record=b.tx_preparation_record()
        self.assertTrue(record['uses_selected_correction'])
        self.assertEqual(len(record['coefficients']),65)
        self.assertAlmostEqual(record['alignment_delay_s'],32/FS)
        self.assertEqual(b.rf.dac_enob,9.)
        self.assertTrue(b.track_rx_pilot_cfo)
        self.assertEqual(b.tx_resampler_span,40)
        self.assertEqual(b.tx_resampler_fraction_bits,14)
        self.assertEqual(b.tx_preparation_metadata['coefficient_fraction_bits'],14)
        old=deepcopy(record)
        b.tx_preemphasis=None
        self.assertTrue(b.tx_preparation_record()['diagnostic_override'])
        self.assertTrue(old['uses_selected_correction'])
        b=ClientBench();b.tx_resampler_span=10
        self.assertTrue(b.tx_preparation_record()['diagnostic_override'])
        self.assertFalse(b.tx_preparation_record()['uses_selected_interpolator'])
        b=ClientBench();b.track_rx_pilot_cfo=False
        self.assertTrue(b.tx_preparation_record()['diagnostic_override'])
        self.assertFalse(b.tx_preparation_record()['uses_selected_frequency_update'])

    def test_direct_rf_path_starts_at_resolved_gain(self):
        from baseline_envelope import configured_environment
        from design_definition import load_design
        from wifi_client_exchange import SharedRFPath
        design=load_design()
        for gain in (-6.,24.,42.):
            config=design.configure(engine='rf',direction='rx',reference_hz=2412e6,
                sample_divider=64,pga_gain_db=gain)
            path=SharedRFPath(environment=configured_environment(config))
            self.assertEqual(path.pga_db,gain)
            self.assertAlmostEqual(path.pga_gain_at(np.array([0.]))[0],10**(gain/20))
            self.assertEqual(path.receiver_context['resolved_configuration'],config.record())

    def test_gain_timing_uses_shared_rates_and_rejects_missing_transport(self):
        import math
        from wifi_client_exchange import SharedRFPath
        from copy import deepcopy
        from baseline_envelope import configured_environment
        from design_definition import load_design,DesignDefinition
        from rf_gain_command import encode_gain
        baseline=load_design();contract=baseline.contract
        contract['transport']['profiles']['ddr156']['clock_hz']=125e6
        design=DesignDefinition.from_documents(contract,baseline.architecture).hypothetical(
            reason='Fast PGA isolates changed host-rate command timing',changes={
                'blocks.pga_i.parameters.gain_response_tau_s':100e-9,
                'blocks.pga_q.parameters.gain_response_tau_s':100e-9})
        config=design.configure(engine='rf',direction='rx',reference_hz=2412e6,
            sample_divider=64,pga_gain_db=27)
        environment=configured_environment(config)
        path=SharedRFPath(environment=environment)
        timing=path.gain_timing()
        self.assertAlmostEqual(timing['parts_s']['return_transport'],192/(2412e6/16))
        self.assertAlmostEqual(timing['parts_s']['command_transport'],192/environment['transport_parameters']['h2d_word_hz'])
        self.assertEqual(timing['inputs']['sample_hz'],config.sample_hz)
        self.assertEqual(timing['inputs']['h2d_words_hz'],250e6)
        self.assertEqual(environment['host_spectrum']['h2d_word_hz'],250e6)
        self.assertEqual(config.record()['h2d_word_hz'],250e6)
        event=path.schedule_gain_command(encode_gain(20,42,0),0,host_issue_s=2e-6,
            tau_s=design.architecture['blocks']['pga_i']['parameters']['gain_response_tau_s'])
        expected_commit=math.ceil((2e-6+192/250e6+12/250e6)*config.sample_hz)/config.sample_hz
        self.assertAlmostEqual(event['commit_s'],expected_commit,places=15)
        environment['transport_parameters']['d2h_word_hz']=1.
        self.assertEqual(path.gain_timing(),timing)
        for key in ('h2d_word_hz','d2h_word_hz'):
            broken=deepcopy(configured_environment(config))
            del broken['transport_parameters'][key]
            with self.assertRaisesRegex(ValueError,'missing transport parameter'):SharedRFPath(environment=broken)
            for value in (1.,float('nan'),True):
                broken=deepcopy(configured_environment(config))
                broken['transport_parameters'][key]=value
                with self.assertRaises(ValueError):SharedRFPath(environment=broken)
        bench=ClientBench(design=design)
        self.assertEqual(bench.chip.a.h2d_clock_scale*312.5e6,250e6)
        self.assertEqual(bench.context_record()['gain_feedback_timing'],bench.rf.gain_timing())
        for value in (None,0.,float('nan'),True):
            broken=design.contract
            if value is None:del broken['transport']['profiles']['ddr156']['clock_hz']
            else:broken['transport']['profiles']['ddr156']['clock_hz']=value
            with self.assertRaises(ValueError):DesignDefinition.from_documents(broken,design.architecture)

    def test_nominal_pga_response_acquires_with_extended_gap(self):
        from wifi_client_exchange import gain_feedback_case
        from design_definition import load_design
        design=load_design()
        result=gain_feedback_case(wanted_dbm=-65.,blocker_dbm=-40.,design=design)
        self.assertNotEqual(result.get('status'),'gain_admission_rejected')
        self.assertTrue(result['decoded'])
        self.assertTrue(result['gain_settled_before_ltf'])
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['gain_response_tau_s'],
            design.architecture['blocks']['pga_i']['parameters']['gain_response_tau_s'])
        self.assertGreater(result['decision'][0]['ready_sample']-result['decision'][0]['commit_sample'],39)
        self.assertEqual(sum(g['count'] for g in result['gaps']),45)
        self.assertEqual(len(result['rf_fixture_parameters']['pga_gain_history']),1)

    def test_supplied_snapshot_reaches_wifi_transport_and_receiver(self):
        from unittest.mock import patch
        from design_definition import load_design,DesignDefinition
        baseline=load_design();contract=baseline.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']*=2
        design=DesignDefinition.from_documents(contract,baseline.architecture).hypothetical(reason='Wi-Fi receiver allocation propagation',changes={
            'blocks.lna.parameters.noise_figure_db':7.25,
            'blocks.lna.parameters.iip3_dbm':-3.,
            'blocks.adc_i.parameters.enob_target':7.,
            'blocks.adc_q.parameters.enob_target':7.,
            'blocks.pga_i.parameters.differential_peak_limit_v':.3,
            'blocks.pga_q.parameters.differential_peak_limit_v':.3})
        with patch('design_definition.load_design',side_effect=AssertionError('unexpected reload')):
            bench=ClientBench(design=design,pga_gain_db=24)
        self.assertEqual(bench.chip.a.startup_s,contract['physical_services']['sar_timing']['startup']['assigned_guard_s'])
        self.assertEqual(bench.chip.a.d2h_clock_scale*312.5e6,2412e6/16)
        with patch('wifi_client_exchange.receive_frontend',return_value=(np.zeros(16,complex),{})) as frontend:
            bench.rf.process(np.zeros(16),'rx')
        self.assertEqual(frontend.call_args.kwargs['noise_figure_db'],7.25)
        self.assertEqual(frontend.call_args.kwargs['input_iip3_dbm'],-3.)
        self.assertEqual(bench.rf.adc_enob,7.)
        self.assertEqual(bench.rf.pga_peak_limit_v,.3)
        self.assertEqual(bench.context_record()['design_provenance'],design.provenance())

    def test_shared_rf_path_rejects_foreign_identity_and_freezes_accepted_context(self):
        from copy import deepcopy
        from wifi_client_exchange import SharedRFPath
        environment=ClientBench().transport_environment
        for missing in ('design_provenance','resolved_configuration'):
            malformed=deepcopy(environment);del malformed[missing]
            with self.assertRaises(ValueError):SharedRFPath(environment=malformed)
        malformed=deepcopy(environment)
        malformed['resolved_configuration']['design_fingerprint']='foreign'
        with self.assertRaisesRegex(ValueError,'conflicts with environment design provenance'):
            SharedRFPath(environment=malformed)
        path=SharedRFPath(environment=environment)
        expected=deepcopy(path.receiver_context)
        environment['design_provenance']['documents'].clear()
        environment['resolved_configuration']['sample_hz']=1.
        self.assertEqual(path.receiver_context,expected)

    def test_wifi_result_metadata_is_independent_of_bench_and_other_reports(self):
        from copy import deepcopy
        bench=ClientBench()
        first=bench.context_record();expected=deepcopy(first)
        second=bench.context_record()
        self.assertEqual(first['scenario_overrides'],bench.transport_environment['scenario_overrides'])
        self.assertEqual(first['operating_conditions'],bench.transport_environment['operating_conditions'])
        second['design_provenance']['documents'].clear()
        second['receiver_allocation']['design_provenance']['documents'].clear()
        second['scenario_overrides'].append({'reason':'report-only mutation'})
        second['scenario_assumptions']['report_only']=True
        second['operating_conditions'].clear()
        self.assertEqual(first,expected)
        self.assertEqual(bench.context_record(),expected)
        bench.transport_environment['scenario_assumptions']['later_fixture']=True
        self.assertEqual(first,expected)
        self.assertTrue(bench.context_record()['scenario_assumptions']['later_fixture'])

    def test_wifi_result_records_current_gain_and_explicit_dac_fixture(self):
        bench=ClientBench(pga_gain_db=24)
        bench.rf.pga_db=42.;bench.rf.dac_enob=9.
        record=bench.context_record()
        self.assertEqual(record['resolved_configuration']['pga_gain_db'],42.)
        self.assertEqual(record['receiver_allocation']['pga_gain_db'],42.)
        self.assertEqual(record['rf_fixture_parameters']['dac_enob'],9.)
        self.assertEqual(record['rf_fixture_parameters']['shared_design_dac_enob'],
            bench.design.architecture['model_assumptions']['paired_dac']['parameters']['enob'])
        self.assertEqual(bench.context_record('tx')['resolved_configuration']['direction'],'tx')
        bench.rf.pga_db=54.
        with self.assertRaisesRegex(ValueError,'PGA setting'):
            bench.context_record()

    def test_event_receiver_uses_shared_pga_limit_before_adc_noise(self):
        from wifi_client_exchange import gain_feedback_case
        from design_definition import load_design
        baseline=load_design()
        limited=baseline.hypothetical(reason='Event-driven PGA headroom propagation',changes={
            'blocks.pga_i.parameters.differential_peak_limit_v':.1,
            'blocks.pga_q.parameters.differential_peak_limit_v':.1})
        results=[gain_feedback_case(wanted_dbm=-50.,blocker_dbm=-40.,design=d)
                 for d in (baseline,limited)]
        self.assertGreater(results[1]['pga_clipped_pairs'],results[0]['pga_clipped_pairs'])
        self.assertEqual(results[1]['receiver_allocation']['pga_nominal_peak_limit_v'],.1)
        self.assertEqual(results[1]['design_provenance'],limited.provenance())
        self.assertEqual(results[1]['adc_clipped_pairs'],0)
