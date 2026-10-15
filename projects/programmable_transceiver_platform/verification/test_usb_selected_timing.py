"""Mixed independent transport controls and shared-design USB exchange checks.

Unconfigured calls are explicit logical fixtures, including zero-startup and
stale-observation faults. Retained lifecycle, ResolvedUSBClockTests and current
budget checks construct shared configurations. Short startup, low rails and
excessive loading remain deliberate fault stimuli, not nominal performance.
"""
import unittest
from usb_selected_timing import response_bound,reply_trace

from design_definition import load_design

TEST_DESIGN_ROLES = {
    'TimingTests': ('independent_fixture', 'Assigned transport timing, credit, CRC and observation-deadline controls; no physical chip budget claim.'),
    'TimingTests.test_current_design_budget_matches_executable_path': ('shared_design', 'Resolves USB configuration and compares shared budget with the configured exchange.'),
    'ChipLifecycleTests': ('shared_design', 'setUp owns one USB configuration; make_chip and reply preserve it. Short startup and observation faults are explicit fixtures.'),
    'ResolvedUSBClockTests': ('shared_design', 'Configured USB clock and budget propagation; hypothetical settings and malformed inputs are intentional controls.'),
}


class TimingTests(unittest.TestCase):
    def test_direct_exchange_requires_fresh_independent_observations(self):
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        from resource_configuration import encode_resource_word
        def setup():
            chip=BehavioralChip(Assumptions(startup_s=0.))
            chip.configure(encode_resource_word(engine='wire'));chip.configure_transport('direct')
            chip.attach_analog_qualification([(0.,True)],max_age_s=200e-9)
            chip.start();chip.advance(0.)
            return chip
        chip=setup()
        result=reply_trace(chip=chip,payload=b'A',analog_observer=lambda t:True)
        self.assertEqual(result['reply_bits'],48)
        self.assertGreater(result['analog_observations'],2)
        for observer,deadline in ((lambda t:None,200e-9),(lambda t:t<150e-9,200e-9)):
            chip=setup()
            with self.assertRaises(AnalogQualificationError):
                reply_trace(chip=chip,payload=b'A',analog_observer=observer)
            self.assertEqual(chip.state,'fault')
            self.assertAlmostEqual(chip.time,deadline,places=15)
            self.assertEqual(chip.direct_session.playback.emitted,0)

    def test_complete_budget(self):
        r=response_bound()
        self.assertAlmostEqual(r['worst_s'],342.25e-9)
        self.assertGreater(r['margin_s'],50e-9)
        self.assertGreater(r['fpga_allowance_s'],170e-9)
        self.assertFalse(response_bound(fpga_s=200e-9)['admissible'])
        self.assertFalse(response_bound(host_hz=60e6)['admissible'])

    def test_causal_ack_phase_sweep(self):
        for host in range(24):
            for read in range(10):
                r=reply_trace(host_phase=host,read_phase=read)
                self.assertEqual(r['reply_bits'],48)
                self.assertEqual(r['scenario_stimuli']['host_phase_ticks'],host)
                self.assertEqual(r['scenario_stimuli']['read_phase_ticks'],read)
                self.assertLessEqual(r['port_start_s'],r['bound_s'])

    def test_long_rx_tx_credit_flow_and_stalls(self):
        for payload in (bytes(1024),bytes([255])*1024,bytes(range(256))*4):
            r=reply_trace(payload=payload,response_payload=payload,stall_every=8)
            self.assertLessEqual(r['peak_staging_bits'],120)
            self.assertEqual(r['scenario_stimuli']['request_payload_hex'],payload.hex())
            self.assertEqual(r['scenario_stimuli']['response_payload_hex'],payload.hex())
            self.assertEqual(r['scenario_stimuli']['response_kind'],'DATA1')
            self.assertEqual(r['scenario_stimuli']['stall_every'],8)

    def test_invalid_crc_or_framing_never_triggers_reply(self):
        result=reply_trace(corrupt=True,payload=b'bad packet',request_delay_ui=7)
        self.assertTrue(result['rejected'])
        self.assertEqual(result['scenario_stimuli']['request_payload_hex'],b'bad packet'.hex())
        self.assertEqual(result['scenario_stimuli']['request_delay_ui'],7)
        self.assertTrue(result['scenario_stimuli']['corrupt_request'])
        self.assertEqual(result['scenario_stimuli']['response_kind'],'ACK')

    def test_late_decision_rejected(self):
        with self.assertRaises(ValueError):reply_trace(fpga_s=200e-9)

    def test_current_design_budget_matches_executable_path(self):
        from usb_selected_timing import configured_response_bound
        design=load_design();a=design.architecture
        budget=a['direct_stream_service']['budget']
        config=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=budget['host_hz'],wired_pad_path='bidirectional')
        bound=configured_response_bound(config)
        result=reply_trace(configuration=config,payload=b'budget-path')
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertAlmostEqual(result['bound_s'],bound['worst_s'],places=15)
        self.assertLessEqual(result['port_start_s'],bound['worst_s'])
        self.assertAlmostEqual(bound['worst_s'],budget['worst_response_s'],places=15)
        self.assertAlmostEqual(bound['margin_s'],budget['margin_s'],places=15)
        self.assertLessEqual(sum(a['resource_policy']['memory_bits'].values()),8192)


class ChipLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.design=load_design()
        self.configuration=self.design.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')

    def make_chip(self,*,startup_s=None):
        from dataclasses import replace
        from behavioral import BehavioralChip
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        assumptions=selected_transport_assumptions(configured_environment(self.configuration))
        if startup_s is not None:
            # Explicit short-guard fixture isolates timeout ordering.
            assumptions=replace(assumptions,startup_s=startup_s)
        chip=BehavioralChip(assumptions)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=self.configuration.line_rate_bps))
        return chip

    def reply(self,**kwargs):
        result=reply_trace(configuration=self.configuration,**kwargs)
        self.assertEqual(result['design_provenance'],self.design.provenance())
        self.assertEqual(result['resolved_configuration'],self.configuration.record())
        return result

    def test_persistent_host_credits_wrap_without_resetting_chip(self):
        from usb_selected_timing import DirectHostState
        from direct_stream import START,word
        chip=self.make_chip()
        chip.configure_transport('direct');chip.start();chip.advance(chip.ready_at)
        host=DirectHostState(chip);epoch=chip.epoch
        for i in range(20):
            result=self.reply(chip=chip,host_state=host,host_phase=7,read_phase=3,
                payload=bytes([i])*13,response_payload=bytes([255-i])*19,stall_every=8)
            self.assertEqual(chip.epoch,epoch)
            self.assertLessEqual(result['port_start_s'],result['bound_s'])
            self.assertLessEqual(host.credits.available,8)
            chip.advance(chip.time+40/2.4e9)  # Explicit peer inter-packet gap.
        self.assertEqual(host.credits.last,chip.direct_session.consumed%32)
        self.assertGreater(chip.direct_session.consumed,32*10)
        self.assertEqual(host.exchanges,20)
        with self.assertRaises(ValueError):DirectHostState(chip)
        self.assertTrue(self.reply(chip=chip,host_state=host,host_phase=7,read_phase=3,
                                   corrupt=True)['rejected'])
        self.assertEqual(chip.state,'active')
        self.assertEqual(self.reply(chip=chip,host_state=host,host_phase=7,read_phase=3)['reply_bits'],48)
        with self.assertRaises(ValueError):self.reply(chip=chip)
        with self.assertRaises(ValueError):chip.direct_session.accept(word(START)^1)
        chip.stop();chip.start();chip.advance(chip.ready_at)
        with self.assertRaises(ValueError):self.reply(chip=chip,host_state=host)
        fresh=DirectHostState(chip)
        self.assertEqual(self.reply(chip=chip,host_state=fresh)['reply_bits'],48)

    def test_direct_exchange_fault_stop_and_new_epoch(self):
        from direct_stream import word, START
        chip=self.make_chip()
        chip.configure_transport('direct')
        old=chip.direct_session
        with self.assertRaises(ValueError):self.reply(chip=chip)
        chip.start();chip.advance(chip.ready_at)
        result=self.reply(chip=chip)
        self.assertEqual(result['reply_bits'],48)
        self.assertGreater(chip.time,chip.a.startup_s)
        with self.assertRaises(ValueError):old.accept(word(START)^1)
        self.assertEqual(chip.state,'fault')
        with self.assertRaises(ValueError):old.tick()
        chip.stop()
        self.assertTrue(old.closed)
        chip.start();chip.advance(chip.ready_at)
        self.assertIsNot(old,chip.direct_session)
        with self.assertRaises(ValueError):old.tick()
        self.assertEqual(self.reply(chip=chip)['reply_bits'],48)

    def test_stop_drops_partial_output_and_rejects_dense_path(self):
        from direct_stream import word, START
        chip=self.make_chip()
        chip.configure_transport('direct');chip.start();chip.advance(chip.ready_at)
        session=chip.direct_session
        session.accept(word(START));session.accept(word(255,True))
        self.assertEqual(session.tick(),1)
        with self.assertRaises(ValueError):
            chip.transfer(mode='wire',source_hz=480e6,sample_bits=1,epoch=chip.epoch)
        chip.stop()
        self.assertEqual(session.playback.bits,0)
        with self.assertRaises(ValueError):session.tick()
        chip.start();chip.advance(chip.ready_at)
        self.assertIsNone(chip.direct_session.tick())

    def test_reference_timeout_interrupts_live_direct_exchange(self):
        from behavioral import ReferenceLossError
        chip=self.make_chip(startup_s=100e-9)
        chip.configure_transport('direct')
        edges=[i*25e-9 for i in range(13)]
        edges += [1e-6+i*25e-9 for i in range(200)]
        chip.attach_reference(edges)
        chip.start();chip.advance(chip.ready_at)
        stale=chip.direct_session
        with self.assertRaises(ReferenceLossError):self.reply(chip=chip)
        self.assertEqual(chip.state,'fault')
        self.assertAlmostEqual(chip.time,400e-9)
        with self.assertRaises(ValueError):stale.tick()
        chip.wait_faulted(1e-6);chip.stop()
        chip.start();chip.advance(chip.ready_at)
        self.assertEqual(self.reply(chip=chip)['reply_bits'],48)

    def test_foreign_shared_pad_rejected_before_exchange_state_advances(self):
        from protocol_pad import SharedWiredPad
        foreign=self.design.hypothetical(reason='Foreign USB pad',changes={
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.})
        chip=self.make_chip()
        pad=SharedWiredPad.from_architecture(foreign.architecture)
        pad.configure('usb',speed='hs');chip.attach_wired_pad(pad)
        before=(chip.time,pad.time)
        with self.assertRaisesRegex(ValueError,'Pad architecture conflicts'):
            self.reply(chip=chip)
        self.assertEqual((chip.time,pad.time),before)
        chip=self.make_chip()
        pad=SharedWiredPad.from_architecture(self.design.architecture)
        pad.configure('usb',speed='hs');chip.attach_wired_pad(pad)
        before=(chip.time,pad.time)
        pad.hs_current*=1.1
        with self.assertRaisesRegex(ValueError,'circuit parameters changed'):
            self.reply(chip=chip)
        self.assertEqual((chip.time,pad.time),before)

    def test_retained_host_cannot_change_design_or_fixture_scope(self):
        from design_definition import DesignDefinition
        from usb_selected_timing import DirectHostState
        chip=self.make_chip()
        chip.configure_transport('direct');chip.start();chip.advance(chip.ready_at)
        host=DirectHostState(chip)
        self.reply(chip=chip,host_state=host,payload=b'A')
        architecture=self.design.architecture
        architecture['direct_stream_service']['budget']['fpga_decision_s']=110e-9
        other=DesignDefinition.from_documents(self.design.contract,architecture).configure(
            engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')
        for config in (other,None):
            before=(chip.time,host.exchanges,host.in_flight,chip.direct_session.consumed)
            with self.subTest(configuration=config),self.assertRaisesRegex(ValueError,'Retained host state'):
                reply_trace(configuration=config,chip=chip,host_state=host,payload=b'B')
            self.assertEqual((chip.time,host.exchanges,host.in_flight,chip.direct_session.consumed),before)
        result=self.reply(chip=chip,host_state=host,payload=b'C')
        self.assertEqual(result['reply_bits'],48)
        self.assertEqual(host.exchanges,2)
        fixture_chip=self.make_chip()
        fixture_chip.configure_transport('direct');fixture_chip.start();fixture_chip.advance(fixture_chip.ready_at)
        fixture_host=DirectHostState(fixture_chip)
        reply_trace(chip=fixture_chip,host_state=fixture_host,payload=b'A')
        with self.assertRaisesRegex(ValueError,'Retained host state'):
            self.reply(chip=fixture_chip,host_state=fixture_host,payload=b'B')
        self.assertFalse(fixture_host.in_flight)
        self.assertEqual(fixture_host.exchanges,1)

    def test_numeric_drive_override_is_not_a_released_pad(self):
        from protocol_pad import SharedWiredPad
        for style in ('current','voltage'):
            chip=self.make_chip()
            chip.configure_transport('direct')
            pad=SharedWiredPad.from_architecture(self.design.architecture)
            pad.configure('usb',speed='hs')
            pad.set_local_drive(style)
            chip.attach_wired_pad(pad)
            chip.start();chip.advance(chip.ready_at)
            before=(chip.time,pad.control_context(),chip.direct_session.consumed)
            with self.subTest(style=style),self.assertRaisesRegex(ValueError,'Released configured HS pad'):
                self.reply(chip=chip,payload=b'A')
            self.assertEqual((chip.time,pad.control_context(),chip.direct_session.consumed),before)

    def test_pad_control_snapshot_separates_peer_and_local_probes(self):
        from protocol_pad import SharedWiredPad
        pad=SharedWiredPad.from_architecture(self.design.architecture)
        pad.configure('usb',role='host',speed='hs')
        pad.set_local_passives(termination_ohm=(42.,48.))
        pad.set_peer_passives(termination_ohm=(45.,45.))
        pad.peer_supply=3.1
        sources=[[.1,50.],None]
        pad.set_external_sources(sources)
        state=pad.control_context()
        sources[0][0]=9.
        self.assertEqual(state['peer']['external_sources_v_ohm'],((.1,50.),None))
        state['peer']['external_sources_v_ohm']=None
        self.assertEqual(pad.external_sources,((.1,50.),None))
        self.assertEqual(state['local']['role'],'host')
        self.assertEqual(state['local']['passive_override']['term'],(42.,48.))
        self.assertEqual(state['peer']['passive_override']['term'],(45.,45.))
        self.assertEqual(state['peer']['supply_v'],3.1)
        self.assertEqual(state['initial_state']['pad_voltage_v'],[0.,0.])
        state['local']['passive_override']['term']=(1.,1.)
        state['initial_state']['pad_voltage_v'][0]=99.
        self.assertEqual(pad.local_passives['term'],(42.,48.))
        self.assertEqual(pad.voltage[0],0.)
        pad.configure('usb',speed='hs')
        self.assertIsNone(pad.control_context()['local']['passive_override'])
        self.assertEqual(pad.control_context()['peer']['passive_override']['term'],(45.,45.))

    def test_exchange_through_retained_shared_pad(self):
        import numpy as np
        from protocol_pad import SharedWiredPad
        from direct_stream import word, START
        chip=self.make_chip()
        chip.configure_transport('direct')
        pad=SharedWiredPad.from_architecture(self.design.architecture)
        pad.configure('usb',speed='hs')
        pad.set_local_passives(termination_ohm=(pad.hs_termination_ohm,)*2)
        pad.set_peer_passives(termination_ohm=(45.,45.))
        chip.attach_wired_pad(pad,rail_source=lambda t:2.9532+.08*np.sin(2*np.pi*1e6*t),max_step_s=50e-9)
        chip.start();chip.advance(chip.ready_at)
        from usb_selected_timing import DirectHostState
        host=DirectHostState(chip)
        result=self.reply(chip=chip,host_state=host,payload=b'A',request_delay_ui=7)
        self.assertEqual(result['pad']['supply'],'time_dependent')
        self.assertEqual(result['pad_supply_input']['kind'],'external_callback')
        self.assertEqual(result['pad_initial_controls']['local']['passive_override']['term'],
                         (pad.hs_termination_ohm,)*2)
        self.assertEqual(result['pad_initial_controls']['local']['drive_state'],'Z')
        self.assertEqual(result['pad_initial_controls']['peer']['drive_state'],'Z')
        self.assertEqual(result['injected_chip_assumptions']['supply_v'],chip.a.supply_v)
        self.assertEqual(result['pad_construction']['architecture_sha256'],
            self.design.provenance()['documents']['spec/analog-architecture.json'])
        result['pad_construction']['probe_overrides']['mutated']=True
        self.assertEqual(pad.construction_context()['probe_overrides'],{})

        self.assertGreater(result['pad']['rx_min_signed_v'],.1)
        self.assertGreater(result['pad']['tx_min_signed_v'],.1)
        self.assertEqual(result['pad']['peer_received_bits'],48)
        chip.advance(chip.time+40/2.4e9)
        self.assertEqual(self.reply(chip=chip,host_state=host,payload=b'C')['reply_bits'],48)
        self.assertEqual(chip.direct_session.playback.completed,2)
        before=np.r_[pad.voltage,pad.divider_voltage].copy()
        chip.stop()
        np.testing.assert_array_equal(np.r_[pad.voltage,pad.divider_voltage],before)
        self.assertIs(chip.wired_pad,pad)
        self.assertEqual(pad.local,'Z')
        chip.start();chip.advance(chip.ready_at)
        self.assertEqual(self.reply(chip=chip,payload=b'B')['reply_bits'],48)
        # Fault releases only local drive, preserving a live peer and capacitance.
        pad.drive(peer='J')
        pad.advance_network(chip.time+1e-9)
        chip.advance(pad.time)
        held=pad.voltage.copy()
        with self.assertRaises(ValueError):chip.direct_session.accept(word(START)^1)
        self.assertEqual(pad.peer,'J')
        np.testing.assert_array_equal(pad.voltage,held)
        self.assertEqual(pad.local,'Z')

    def test_in_packet_squelch_erasure_cannot_reply_and_stop_allows_recovery(self):
        from protocol_pad import SharedWiredPad
        from usb_selected_timing import DirectHostState
        chip=self.make_chip()
        chip.configure_transport('direct')
        pad=SharedWiredPad.from_architecture(self.design.architecture);pad.configure('usb',speed='hs')
        pad.set_local_passives(termination_ohm=(pad.hs_termination_ohm,)*2)
        pad.set_peer_passives(termination_ohm=(45.,45.))
        chip.attach_wired_pad(pad);chip.start();chip.advance(chip.ready_at)
        host=DirectHostState(chip)
        with self.assertRaisesRegex(ValueError,'acquisition/framing'):
            self.reply(chip=chip,host_state=host,payload=b'A',request_dropout_ui=(40,41))
        self.assertEqual(chip.direct_session.playback.emitted,0)
        self.assertEqual(pad.local,'Z')
        chip.stop();chip.start();chip.advance(chip.ready_at)
        self.assertIs(chip.wired_pad,pad)
        recovered=self.reply(chip=chip,host_state=DirectHostState(chip),payload=b'B')
        self.assertEqual(recovered['reply_bits'],48)
        self.assertEqual(recovered['pad_supply_input'],dict(kind='constant_fixture',voltage_v=chip.a.supply_v))

    def test_low_pad_supply_prevents_ideal_reply_success(self):
        from protocol_pad import SharedWiredPad
        chip=self.make_chip()
        chip.configure_transport('direct')
        pad=SharedWiredPad.from_architecture(self.design.architecture);pad.configure('usb',speed='hs')
        pad.set_local_passives(termination_ohm=(pad.hs_termination_ohm,)*2)
        pad.set_peer_passives(termination_ohm=(45.,45.))
        chip.attach_wired_pad(pad,rail_source=lambda t:.05,max_step_s=1e-6)
        chip.start();chip.advance(chip.ready_at)
        with self.assertRaisesRegex(ValueError,'Reply below pad squelch'):
            self.reply(chip=chip,payload=b'A')
        chip.stop()
        self.assertEqual(pad.local,'Z')

    def test_excessive_pad_loading_cannot_inherit_ideal_decode(self):
        from protocol_pad import SharedWiredPad
        chip=self.make_chip()
        chip.configure_transport('direct')
        pad=SharedWiredPad(cap_f=1e-9)
        pad.configure('usb',speed='hs')
        pad.set_local_passives(termination_ohm=(45.,45.))
        pad.set_peer_passives(termination_ohm=(45.,45.))
        chip.attach_wired_pad(pad);chip.start();chip.advance(chip.ready_at)
        with self.assertRaisesRegex(ValueError,'squelch'):
            self.reply(chip=chip,payload=b'A')
        self.assertEqual(chip.direct_session.playback.emitted,0)


class ResolvedUSBClockTests(unittest.TestCase):
    def configuration(self):
        return load_design().configure(engine='wire',direction='duplex',reference_hz=480e6,
                                       host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')

    def test_exchange_consumes_the_selected_host_follow_clock(self):
        config=self.configuration()
        result=reply_trace(configuration=config,host_phase=19,read_phase=9,payload=b'A')
        self.assertEqual(result['host_word_hz'],100e6)
        self.assertEqual(result['resolved_configuration'],config.record())
        self.assertGreaterEqual(result['margin_s'],0.)
        self.assertEqual(result['result_role'],'configured_component_fixture')

    def test_mismatched_host_clocks_are_not_silently_accepted(self):
        from behavioral import BehavioralChip,Assumptions
        config=self.configuration()
        with self.assertRaisesRegex(ValueError,'Host rate conflicts'):
            reply_trace(configuration=config,host_hz=120e6)
        with self.assertRaisesRegex(ValueError,'Chip host clocks'):
            reply_trace(configuration=config,chip=BehavioralChip(Assumptions()))

    def test_injected_chip_engine_rate_and_startup_are_accounted_for(self):
        from behavioral import BehavioralChip,Assumptions
        config=self.configuration()
        assumptions=Assumptions(h2d_clock_scale=.32,d2h_clock_scale=.32,startup_s=100e-9)
        for rate in (None,1.25e9):
            chip=BehavioralChip(assumptions)
            if rate is not None:chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=rate))
            with self.subTest(rate=rate),self.assertRaisesRegex(ValueError,'engine/line rate'):
                reply_trace(configuration=config,chip=chip)
        chip=BehavioralChip(assumptions)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=480e6))
        chip.configure_transport('direct');chip.start();chip.advance(chip.ready_at)
        result=reply_trace(configuration=config,chip=chip,payload=b'A')
        self.assertEqual(result['reply_bits'],48)
        override=result['diagnostic_model_overrides'][0]
        self.assertEqual(override['parameter'],'startup_s')
        self.assertEqual(override['value'],100e-9)
        self.assertEqual(override['design_value'],20e-6)
        self.assertIn('no nominal startup qualification',override['reason'])

    def test_injected_assumptions_survive_acceptance_and_rejection(self):
        from dataclasses import asdict
        from behavioral import BehavioralChip,Assumptions
        config=self.configuration()
        assumptions=Assumptions(h2d_clock_scale=.32,d2h_clock_scale=.32,
                                startup_s=0.,supply_v=3.1)
        for corrupt in (False,True):
            chip=BehavioralChip(assumptions)
            chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=480e6))
            chip.configure_transport('direct');chip.start();chip.advance(chip.ready_at)
            result=reply_trace(configuration=config,chip=chip,payload=b'A',corrupt=corrupt)
            self.assertEqual(result['reply_bits'],0 if corrupt else 48)
            self.assertEqual(result['injected_chip_assumptions'],asdict(assumptions))
            self.assertIn('not shared-design qualification',result['injected_chip_assumptions_scope'])
            self.assertIsNone(result['pad_supply_input'])
            result['injected_chip_assumptions']['supply_v']=9.
            self.assertEqual(chip.a.supply_v,3.1)

    def test_budget_and_exchange_reject_non_usb_configurations(self):
        from usb_selected_timing import configured_response_bound
        design=load_design()
        configurations=[None,{},
            design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                sample_divider=64,pga_gain_db=39),
            design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)]
        for config in configurations:
            with self.subTest(configuration=config):
                with self.assertRaisesRegex(ValueError,'resolved bidirectional 480 Mb/s'):
                    configured_response_bound(config)
                # None explicitly selects the independent exchange fixture.
                if config is not None:
                    with self.assertRaisesRegex(ValueError,'resolved bidirectional 480 Mb/s'):
                        reply_trace(configuration=config)

    def test_configured_budget_matches_independent_analytical_fixture(self):
        from usb_selected_timing import configured_response_bound
        actual=configured_response_bound(self.configuration())
        expected=response_bound()
        self.assertEqual(actual,expected)
        self.assertAlmostEqual(actual['worst_s'],342.25e-9,places=15)

    def test_design_allocations_reach_exchange_and_missing_values_fail(self):
        from design_definition import DesignDefinition
        design=load_design();architecture=design.architecture
        budget=architecture['direct_stream_service']['budget']
        budget['analog_output_s']=26e-9
        budget['fpga_decision_s']=110e-9
        changed=DesignDefinition.from_documents(design.contract,architecture)
        config=changed.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')
        result=reply_trace(configuration=config,payload=b'A')
        self.assertEqual(result['fpga_decision_s'],110e-9)
        self.assertEqual(result['response_budget']['costs_s']['analog'],26e-9)
        self.assertEqual(result['design_provenance'],changed.provenance())
        self.assertNotEqual(changed.fingerprint,design.fingerprint)
        self.assertEqual(result['timing_allocation_overrides'],[])
        override=reply_trace(configuration=config,payload=b'A',fpga_s=100e-9)
        self.assertEqual(override['timing_allocation_overrides'][0]['design_value'],110e-9)
        del budget['analog_output_s']
        with self.assertRaisesRegex(ValueError,'Missing required design parameter'):
            DesignDefinition.from_documents(design.contract,architecture)

    def test_unimplemented_pipeline_is_rejected_before_exchange(self):
        from design_definition import DesignDefinition
        design=load_design();architecture=design.architecture
        architecture['direct_stream_service']['budget']['rx_cdc_host_cycles']=4
        changed=DesignDefinition.from_documents(design.contract,architecture)
        config=changed.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')
        with self.assertRaisesRegex(ValueError,'does not implement.*rx_cdc_host_cycles'):
            reply_trace(configuration=config)
