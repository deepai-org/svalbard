"""Independent packet vectors/observers plus shared-inventory RX/TX packet checks.

Joined checks use explicit wanted/blocker stimuli and assigned-ENOB conversion.
The electrical seed has prescribed clock/reference spectra; it does not qualify
loaded differential REF_IN, retained SAR feedback or physical RF turnaround.
"""
import unittest
import copy
import json
import numpy as np
from ble_packet import (P,observe,bounded_gain_conversion,joined_scan_request,response_budget,
    transmitted_scan_response)
from protocol_signals import ble_advertising_bits,ble_whiten,ble_crc_bits,gfsk

from design_definition import load_design

TEST_DESIGN_ROLES = {
    'BLEPacketTests': ('independent_fixture', 'Published packet vector, blind decoder, PRBS and independent gain/nonlinearity examples.'),
    'JoinedPacketTests': ('shared_design', 'One class-owned snapshot supplies RX/TX configurations and allocations; packet levels and diagnostic impairments are explicit stimuli.'),
    'TimedPlaybackTests': ('independent_fixture', 'Assigned playback queues and analytical RF power/Parseval examples.'),
}

class BLEPacketTests(unittest.TestCase):
    def test_prbs15_interferer_period_and_constant_envelope(self):
        from ble_packet import prbs15_bits,reference_interferer_phase
        bits=prbs15_bits(32767+15)
        np.testing.assert_array_equal(bits[:15],bits[32767:])
        self.assertEqual(int(bits[:32767].sum()),16384)
        # Every nonzero 15-bit word occurs once: checks the full maximal period.
        words={sum(int(bits[i+j])<<j for j in range(15)) for i in range(32767)}
        self.assertEqual(len(words),32767);self.assertNotIn(0,words)
        times=np.arange(4001)/40e6;phase=reference_interferer_phase(times)
        np.testing.assert_allclose(abs(np.exp(1j*phase)),1.,atol=1e-15)
        deviation=np.diff(phase)*40e6/(2*np.pi)
        self.assertLessEqual(max(abs(deviation)),250000.0001)
        self.assertGreater(np.std(deviation),1e5)
        np.testing.assert_allclose(reference_interferer_phase(times[::4]),phase[::4],atol=1e-12)

    def test_input_referred_cubic_matches_two_tone_intercept(self):
        from ble_packet import third_order_frontend
        t=np.arange(4096)/16e6
        for power_dbm in (-50.,-44.):
            peak=np.sqrt(2*50*1e-3*10**(power_dbm/10))
            x=peak*(np.exp(2j*np.pi*1e6*t)+np.exp(2j*np.pi*2e6*t))
            y,info=third_order_frontend(x,-10.)
            im3_w=abs(np.mean(y))**2/(2*50)
            self.assertAlmostEqual(10*np.log10(im3_w/1e-3),3*power_dbm+20,places=7)
            self.assertTrue(info['within_assigned_small_compression_range'])
        _,info=third_order_frontend(np.ones(10),-20.)
        self.assertFalse(info['within_assigned_small_compression_range'])

    def test_gain_control_is_delayed_bounded_and_causal(self):
        signal=np.full(400,1e-4+0j);noise=np.zeros(400,complex)
        whole,trace=bounded_gain_conversion(signal,noise,command_latency_s=2e-6)
        prefix,short=bounded_gain_conversion(signal[:100],noise[:100],command_latency_s=2e-6)
        self.assertTrue(np.array_equal(whole[:100],prefix))
        self.assertEqual(trace['gain_db'][:100],short['gain_db'])
        self.assertTrue(all(g==40. for g in trace['gain_db'][:30]))
        self.assertGreater(trace['gain_db'][31],40.)
        self.assertLessEqual(max(trace['gain_db']),60.)
        _,clipped=bounded_gain_conversion(np.ones(100),np.zeros(100))
        self.assertGreater(clipped['pga_clipped_samples'],0)
        self.assertLess(clipped['gain_db'][-1],40.)

    def test_bluetooth_published_legacy_advertising_vector(self):
        # Core 6.1 Vol 6 C 4.2.1, transmission order left to right.
        pdu=bytes.fromhex('4209a6a5a4a3a2c1010203')
        expected=('01010101 01101011 01111101 10010001 01110001 '
            '00101001 00110011 01000111 10100001 10111111 10111110 '
            '11000010 01110010 01011000 11100101 00110101 11110111 11110011 10100101')
        bits=ble_advertising_bits(pdu,38)
        self.assertEqual(''.join(map(str,bits)),expected.replace(' ',''))
        data=ble_whiten(bits[40:],38)
        self.assertTrue(np.array_equal(ble_crc_bits(data[:-24]),data[-24:]))

    def capture(self,bits):
        wave=gfsk(bits,fs=10e6)
        samples=wave.samples[20:20+10*len(bits)]
        z=np.r_[np.zeros(73),samples,np.zeros(100)]
        return .2*z*np.exp(2j*np.pi*73000*np.arange(len(z))/10e6)

    def test_observer_has_no_payload_start_or_frequency_oracle(self):
        pdu=bytes.fromhex('4209a6a5a4a3a2c1010203')
        result=observe(self.capture(ble_advertising_bits(pdu)))
        self.assertTrue(result['crc_ok'])
        self.assertEqual(result['pdu_hex'],pdu.hex())
        self.assertLess(abs(result['cfo_estimate_hz']-73000),10000)

    def test_corruption_and_noise_are_not_valid_packets(self):
        bits=ble_advertising_bits(bytes.fromhex('4209a6a5a4a3a2c1010203'))
        bits[75]^=1
        self.assertFalse(observe(self.capture(bits))['crc_ok'])
        rng=np.random.default_rng(21)
        noise=rng.normal(size=2000)+1j*rng.normal(size=2000)
        self.assertFalse(observe(noise)['crc_ok'])
        self.assertFalse(observe(np.zeros(2000))['crc_ok'])

    def test_acquisition_is_independent_of_future_payload(self):
        bits=ble_advertising_bits(bytes.fromhex('4209a6a5a4a3a2c1010203'))
        capture=self.capture(bits);full=observe(capture)
        end=full['acquisition_decision_sample']
        prefix=observe(capture[:end])
        self.assertTrue(prefix['acquired'])
        self.assertFalse(prefix['crc_ok'])
        self.assertFalse(observe(capture[:end-1])['acquired'])
        rng=np.random.default_rng(831)
        changed=capture.copy();changed[end:]=rng.normal(size=len(changed)-end)+1j*rng.normal(size=len(changed)-end)
        future=observe(changed)
        for key in ('start_sample','cfo_estimate_hz','fit_residual','acquisition_decision_sample'):
            self.assertEqual(full[key],prefix[key])
            self.assertEqual(full[key],future[key])

class JoinedPacketTests(unittest.TestCase):
    """Shared RX/TX snapshots; known stimuli and simplified converter/readiness laws."""
    @classmethod
    def setUpClass(cls):
        from baseline_envelope import configured_environment
        cls.design=load_design();cls.contract=cls.design.contract
        cls.rx_config=cls.design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                           sample_divider=64,pga_gain_db=39)
        cls.tx_config=cls.design.configure(engine='rf',direction='tx',reference_hz=2.426e9,
                                           sample_divider=64)
        cls.environment=configured_environment(cls.rx_config)
        cls.tx_environment=configured_environment(cls.tx_config)
        cls.received=cls.receive()

    @classmethod
    def receive(cls,**kwargs):
        # Explicit wanted/blocker stimuli; no gain or noise-budget fitting to decoding.
        return joined_scan_request(cls.environment,cls.contract,
            **dict(dict(wanted_dbm=-67.,blocker_dbm=-50.),**kwargs))

    def test_receive_report_owns_its_configuration_metadata(self):
        row=self.receive()
        before=copy.deepcopy(self.environment['resolved_configuration'])
        row['resolved_configuration']['sample_divider']=999
        row['scenario_overrides'].append({'test_only':'mutation'})
        self.assertEqual(self.environment['resolved_configuration'],before)
        self.assertEqual(self.environment['scenario_overrides'],[])
        self.assertEqual(self.received['resolved_configuration'],before)

    def test_noise_requirement_controls_preserve_units_and_independence(self):
        low=self.receive(noise_figure_db=0.,adc_enob=10.)
        self.assertAlmostEqual(self.received['thermal_noise_density_v2_per_hz']/low['thermal_noise_density_v2_per_hz'],
                               10**(self.design.architecture['blocks']['lna']['parameters']['noise_figure_db']/10))
        a=self.receive(thermal_noise_enabled=False,noise_figure_db=0.)
        b=self.receive(thermal_noise_enabled=False,noise_figure_db=10.)
        self.assertEqual(a['observation'],b['observation'])
        self.assertEqual(a['gain_control'],b['gain_control'])
        self.assertTrue(a['adc_noise_enabled'])
        self.assertFalse(a['thermal_noise_enabled'])
        with self.assertRaises(ValueError):self.receive(adc_enob=13.)

    def budget(self,observation=None,environment=None,**kwargs):
        return response_budget(observation or self.received['observation'],self.received['settings'],
            environment or self.environment,self.contract,
            advertiser_address=bytes.fromhex('a6a5a4a3a2c1'),**kwargs)

    def test_response_budget_rejects_conflicting_sample_rate_and_missing_clock(self):
        settings=dict(self.received['settings'],sample_hz=self.received['settings']['sample_hz']*2)
        with self.assertRaisesRegex(ValueError,'sample rate conflicts'):
            response_budget(self.received['observation'],settings,self.environment,self.contract,
                advertiser_address=bytes.fromhex('a6a5a4a3a2c1'))
        missing=dict(self.environment);del missing['control_hz']
        with self.assertRaisesRegex(ValueError,'requires control clock'):
            self.budget(environment=missing)
        for value in (None,0.,-1.,True,float('nan')):
            for environment,call in (
                (self.environment,lambda env:joined_scan_request(env,self.contract)),
                (self.tx_environment,lambda env:transmitted_scan_response(self.received,env,self.contract))):
                damaged=copy.deepcopy(environment)
                if value is None:del damaged['control_hz']
                else:damaged['control_hz']=value
                with self.subTest(value=value,direction=environment['resolved_configuration']['direction']),self.assertRaises(ValueError):
                    call(damaged)
        from ble_packet import packet_control_clock
        self.assertEqual(packet_control_clock({}),40e6)

    def test_real_packet_and_causal_reply_budget_keep_clocks_running(self):
        row=self.received;reply=row['response']
        self.assertEqual(row['control_counter_hz'],self.environment['control_hz'])
        self.assertEqual(reply['control_counter_hz'],self.environment['control_hz'])
        self.assertEqual(row['design_provenance'],self.design.provenance())
        self.assertEqual(row['resolved_configuration'],self.rx_config.record())
        self.assertTrue(row['correct_request'])
        self.assertTrue(reply['reply_armed'])
        self.assertFalse(reply['air_launch_timing_verified'])
        self.assertGreater(row['adc_crossing_rms_s'],0.)
        self.assertLess(row['gain_control']['reference_scale_min'],1.)
        self.assertGreater(row['gain_control']['reference_scale_max'],1.)
        self.assertEqual(reply['turnaround']['old_d2h_clock_hz'],2.426e9/32)
        self.assertTrue(reply['turnaround']['clocks_kept_running'])
        self.assertEqual(reply['turnaround']['old_epoch'],reply['turnaround']['new_epoch'])
        self.assertGreater(reply['ready_s'],row['observation']['crc_decision_s']+32/row['settings']['sample_hz'])
        self.assertLess(reply['transport']['tx_prefill_plus_service_backlog_bits'],
            self.contract['transport']['scheduling']['ingress_bits_per_source'])
        for a,b in zip(reply['events'],reply['events'][1:]):
            self.assertEqual(a['end_s'],b['start_s'])
        # Delaying FPGA computation cannot advance the response or repair a
        # missed deadline by using the source's true packet-end timestamp.
        late=self.budget(fpga_work_s=160e-6)
        self.assertFalse(late['reply_armed'])
        self.assertAlmostEqual(late['ready_s']-reply['ready_s'],158e-6,places=12)
        self.assertEqual(late['target_air_start_s'],reply['target_air_start_s'])

    def test_packet_supply_laws_follow_changed_shared_design(self):
        from unittest.mock import patch
        import ble_packet
        from baseline_envelope import configured_environment
        variant=self.design.hypothetical(reason='Packet supply-law propagation control',changes={
            'model_assumptions.rf_receive_supply.parameters.gain_reference_v':3.0,
            'model_assumptions.rf_receive_supply.parameters.headroom_reference_v':3.1,
            'blocks.rfdriver.parameters.gain_reference_v':3.2})
        environments=[self.environment,configured_environment(variant.configure(
            engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=64,pga_gain_db=39))]
        amplitudes=[];rows=[];original=ble_packet.multipole_envelope
        def observe(signal,*args,**kwargs):
            amplitudes.append(float(np.max(abs(signal))))
            return original(signal,*args,**kwargs)
        for environment in environments:
            with patch.object(ble_packet,'multipole_envelope',side_effect=observe):
                rows.append(joined_scan_request(environment,self.contract,wanted_dbm=-67.,blocker_dbm=-50.))
        self.assertEqual(len(amplitudes),2)
        rail=self.environment['ledger']['local_payload_clock_core_rail_v']
        elasticity=self.environment['rf_receive_supply_parameters']['gain_supply_elasticity']
        expected=(1+elasticity*(rail/3.0-1))/(1+elasticity*(rail/3.3-1))
        self.assertAlmostEqual(amplitudes[1]/amplitudes[0],expected,places=12)
        self.assertAlmostEqual(rows[1]['gain_control']['pga_peak_v']/rows[0]['gain_control']['pga_peak_v'],3.3/3.1,places=12)
        self.assertEqual(rows[1]['design_provenance'],variant.provenance())
        missing=copy.deepcopy(environments[1]);del missing['rf_receive_supply_parameters']
        with self.assertRaises(ValueError):joined_scan_request(missing,self.contract)
        tx_environment=configured_environment(variant.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64))
        normal=transmitted_scan_response(self.received,self.tx_environment,self.contract)
        changed=transmitted_scan_response(self.received,tx_environment,self.contract)
        self.assertEqual(changed['driver_settings']['gain_reference_v'],3.2)
        self.assertAlmostEqual(changed['loaded_peak_envelope_v']/normal['loaded_peak_envelope_v'],3.3/3.2,places=12)
        self.assertAlmostEqual(changed['loaded_average_active_power_w']/normal['loaded_average_active_power_w'],(3.3/3.2)**2,places=12)
        self.assertEqual(changed['design_provenance'],variant.provenance())

    def test_reply_reports_its_own_supply_domain_not_received_packet_bounds(self):
        environment=copy.deepcopy(self.tx_environment)
        environment['ledger']['local_payload_clock_core_rail_v']=2.4
        low=transmitted_scan_response(self.received,environment,self.contract)
        self.assertEqual(low['evaluated_supply_interval_v'],[2.4,2.4])
        self.assertFalse(low['evaluated_supply_valid'])
        normal=transmitted_scan_response(self.received,self.tx_environment,self.contract,dynamic_rail=True)
        self.assertTrue(normal['evaluated_supply_valid'])
        self.assertGreater(normal['evaluated_supply_interval_v'][1],normal['evaluated_supply_interval_v'][0])

    def test_fast_sample_prefill_fits_existing_fifo_and_plays_reply(self):
        received=self.receive(lo_divider=64)
        reply=received['response'];service=reply['transport']
        self.assertTrue(reply['reply_armed'])
        self.assertLess(service['prefill_bits'],32*24)
        self.assertGreaterEqual(service['prefill_bits'],service['h2d']['backlog_bound_bits'])
        self.assertLessEqual(service['tx_prefill_plus_service_backlog_bits'],
            self.contract['transport']['scheduling']['ingress_bits_per_source'])
        transmitted=transmitted_scan_response(received,self.tx_environment,self.contract)
        self.assertTrue(transmitted['playback']['complete_burst'])
        self.assertTrue(transmitted['peer_correct_response'])

    def test_reply_requires_integrity_address_and_sustained_service(self):
        observation=dict(self.received['observation'],crc_ok=False)
        self.assertFalse(self.budget(observation)['reply_armed'])
        decoded=bytearray.fromhex(self.received['observation']['pdu_hex'])
        decoded[-1]^=1
        observation=dict(self.received['observation'],pdu_hex=decoded.hex())
        self.assertFalse(self.budget(observation)['request_accepted'])
        constrained=copy.deepcopy(self.environment)
        constrained['host_spectrum']['h2d_word_hz']=1e6
        self.assertFalse(self.budget(environment=constrained)['reply_armed'])

    def test_resolved_mixer_refinement_preserves_acquisition_and_packet(self):
        coarse=self.receive(include_noise=False,mixer_substeps=256)
        fine=self.receive(include_noise=False,mixer_substeps=512)
        self.assertTrue(coarse['correct_request'] and fine['correct_request'])
        self.assertEqual(coarse['observation']['start_sample'],fine['observation']['start_sample'])
        self.assertEqual(coarse['adc_crossing_rms_s'],fine['adc_crossing_rms_s'])
        self.assertLess(abs(coarse['observation']['cfo_estimate_hz']-fine['observation']['cfo_estimate_hz']),500.)
        self.assertLess(abs(coarse['observation']['fit_residual']-fine['observation']['fit_residual']),.003)

    def test_loaded_reply_decodes_without_source_end_oracle(self):
        transmitted=transmitted_scan_response(self.received,self.tx_environment,self.contract)
        self.assertTrue(transmitted['peer_correct_response'])
        self.assertTrue(transmitted['playback']['complete_burst'])
        # The /64, 312.5 Mword/s fixture uses a 25-sample bounded-service prefill.
        self.assertEqual(transmitted['playback']['peak_occupancy_samples'],25)
        self.assertEqual(transmitted['design_provenance'],self.design.provenance())
        self.assertEqual(transmitted['resolved_configuration'],self.tx_config.record())
        self.assertGreater(transmitted['playback']['prelaunch_clock_edges_without_consumption'],1000)
        self.assertFalse(transmitted['phase_time_origin_reset'])
        self.assertFalse(transmitted['air_launch_timing_qualified'])
        # The source boundary is an offline scoreboard input only, never used
        # to set launch timing or help the peer decode.
        changed=dict(self.received,source_packet_end_s=self.received['source_packet_end_s']+1e-3)
        other=transmitted_scan_response(changed,self.tx_environment,self.contract)
        self.assertEqual(other['first_dac_consumption_s'],transmitted['first_dac_consumption_s'])
        self.assertEqual(other['peer'],transmitted['peer'])
        self.assertAlmostEqual(other['scoreboard_rf_half_amplitude_gap_s'],
            transmitted['scoreboard_rf_half_amplitude_gap_s']-1e-3,places=12)

    def test_tx_calibration_changes_launch_and_host_stall_is_not_hidden(self):
        baseline=transmitted_scan_response(self.received,self.tx_environment,self.contract)
        corrected=transmitted_scan_response(self.received,self.tx_environment,self.contract,
            rx_timestamp_correction_s=.8e-6,tx_launch_advance_s=.15e-6)
        self.assertTrue(corrected['peer_correct_response'])
        self.assertLess(abs(corrected['scoreboard_rf_half_amplitude_gap_s']-150e-6),
            abs(baseline['scoreboard_rf_half_amplitude_gap_s']-150e-6))
        self.assertAlmostEqual(baseline['desired_launch_s']-corrected['desired_launch_s'],.95e-6,places=12)
        stalled=transmitted_scan_response(self.received,self.tx_environment,self.contract,host_gap_s=10e-6)
        self.assertEqual(stalled['playback']['fault'],'underflow')
        self.assertEqual(stalled['playback']['consumed_samples'],25)
        self.assertFalse(stalled['peer_correct_response'])


class TimedPlaybackTests(unittest.TestCase):
    def test_rf_power_units_and_offset_bands_against_known_tones(self):
        from ble_packet import rf_emission_bands
        times=np.arange(4096)/1e9
        for frequency,band in ((0.,'within_1mhz'),(125e6,'offset_above_40mhz')):
            result=rf_emission_bands(np.exp(2j*np.pi*frequency*times),1e9)
            # A 1 V peak RF envelope into 50 ohms dissipates 10 mW.
            self.assertAlmostEqual(result['window_weighted_total_w'],.01,places=12)
            self.assertAlmostEqual(result['band_power_w'][band],.01,places=8)
            self.assertLess(abs(result['parseval_residual_w']),1e-14)

    def test_clocked_wait_preserves_prefill_and_sample_order(self):
        from behavioral import timed_dac_playback
        samples=np.arange(1,65)/100+0j
        edges=np.arange(170)/1e6;launch=100e-6
        arrivals=np.r_[np.full(32,1e-6),launch+np.arange(1,33)/1e6+3e-6]
        played,result=timed_dac_playback(samples,arrivals,edges,launch_s=launch,
            depth_samples=42,minimum_prefill_samples=32)
        np.testing.assert_array_equal(played[edges<launch],0.)
        np.testing.assert_array_equal(played[100:164],samples)
        self.assertTrue(result['complete_burst'])
        self.assertEqual(result['peak_occupancy_samples'],32)

    def test_underflow_latches_mute_even_when_data_arrives_later(self):
        from behavioral import timed_dac_playback
        samples=np.ones(64,complex);edges=np.arange(170)/1e6;launch=100e-6
        arrivals=np.r_[np.full(32,1e-6),launch+np.arange(1,33)/1e6+40e-6]
        played,result=timed_dac_playback(samples,arrivals,edges,launch_s=launch,
            depth_samples=42,minimum_prefill_samples=32)
        self.assertEqual(result['fault'],'underflow')
        np.testing.assert_array_equal(played[100:132],1.)
        np.testing.assert_array_equal(played[132:],0.)

if __name__=='__main__':unittest.main()
