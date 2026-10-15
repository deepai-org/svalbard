"""Design snapshot identity, isolation, and missing-input boundaries."""
import json
from pathlib import Path
import sys
import unittest

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P/'system_model/architecture_fast'))
from design_definition import DesignDefinition, load_design


TEST_DESIGN_ROLES = {
    'DesignDefinitionTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ResolvedConfigurationTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ScenarioBindingTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'CalibrationObservationSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReceiverSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HypotheticalCircuitTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'PacketFactoryTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'SharedNetworkTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'LoadedClockSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ConverterOwnershipTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'OperatingAssumptionTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'NarrowbandConfigurationTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'WiredConfigurationTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'TransmitterConfigurationTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ExplicitExperimentTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'SnapshotEntryTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'WiredProbeSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'RFFeedManifestTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'PreemphasisSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'USBInventorySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'PacketScreenSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'TransmitScreenSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ConverterScreenSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'CDRScreenSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'USBPacketSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'DiagnosticEnvironmentBindingTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReferenceAcceptanceSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReferenceSupplySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'FilterBudgetSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'SharedPadEntrySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'CommonEnvelopeSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'RFChainSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'FilterProbeSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'CurrentProbeSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'TurnaroundSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'DirectionControlSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'TransportAssumptionSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HostFollowTransportSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'FeedRFProbeSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'PhaseBoundSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'USBFeedSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReferenceCampaignSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReferenceRequirementSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ReferenceStartupSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HandoverSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'FiniteReplaySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ExtendedReplaySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'RetuneSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ClockLossSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HandoverPackageOverrideTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'LifecycleSnapshotForwardingTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'MonitorRecoverySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'USBSupplySnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ClockScreenSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'DecouplingSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HostSpectrumRateBindingTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'HostChargeOwnershipTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'RevisionCommandSnapshotTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'CampaignSnapshotPropagationTests': ('shared_design', 'Shared snapshot/configuration propagation and rejection guards; malformed inputs and mocked boundaries are explicit controls.'),
    'ScenarioBindingTests.test_uncertainty_cannot_smuggle_in_hardware_settings_or_unapplied_inputs': ('independent_fixture', 'Independent malformed Scenario API inputs; no chip simulation.'),
    'PacketFactoryTests.test_packet_stimulus_uses_actual_supplied_bytes': ('independent_fixture', 'Independent packet encoder/decoder stimulus check.'),
    'ConverterOwnershipTests.test_frontend_thermal_noise_obeys_temperature_scaling': ('independent_fixture', 'Assigned temperatures and matched random draws checked against thermal-noise scaling.'),
    'WiredProbeSnapshotTests.test_baseline_runner_rejects_source_changes_and_records_stable_snapshot': ('independent_fixture', 'Mocked campaign outputs and source hashes isolate write-time freshness enforcement.'),
    'WiredProbeSnapshotTests.test_adverse_pulse_budget_failure_is_reported_without_masking_other_errors': ('independent_fixture', 'Injected exceptions isolate campaign rejection routing.'),
    'PacketScreenSnapshotTests.test_reference_clock_flag_is_json_serializable': ('independent_fixture', 'Assigned tone and reference amplitude check JSON-compatible scalar output.'),
    'ReferenceSupplySnapshotTests.test_reference_probe_manifest_detects_source_drift': ('independent_fixture', 'Source-hash integrity and deliberately corrupted manifest; no circuit behavior.'),
    'TransportAssumptionSnapshotTests.test_independent_transport_fixture_can_retain_primitive_assumptions': ('independent_fixture', 'Explicit independent host rates verify primitive transport defaults remain available.'),
    'LifecycleSnapshotForwardingTests.test_bound_lifecycle_functions_do_not_reload_converter_defaults': ('independent_fixture', 'Static source guard against reloading defaults; does not simulate a chip.'),
    'LifecycleSnapshotForwardingTests.test_campaign_orchestrators_forward_their_snapshot_to_design_aware_children': ('independent_fixture', 'Static source guard verifies snapshot forwarding at orchestrator call sites.'),
}

class DesignDefinitionTests(unittest.TestCase):
    def test_reference_pad_and_timing_ownership_fail_at_load(self):
        design=load_design()
        for value in (None,0,-1,True,'2.7pF'):
            architecture=design.architecture
            if value is None:del architecture['blocks']['refpad']['parameters']['capacitance_f_per_leg']
            else:architecture['blocks']['refpad']['parameters']['capacitance_f_per_leg']=value
            with self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)
        for key in ('supply_sensitivity_ps_per_mv','delay_pole_hz'):
            architecture=design.architecture
            architecture['blocks']['refinput']['parameters'][key]=1.
            with self.assertRaisesRegex(ValueError,'Duplicate reference timing'):
                DesignDefinition.from_documents(design.contract,architecture)
            architecture=design.architecture
            architecture['blocks']['refinput']['shared_parameter_sources'][key]='stale.owner'
            with self.assertRaisesRegex(ValueError,'parameter owner'):
                DesignDefinition.from_documents(design.contract,architecture)

    def test_cdr_detector_and_holdover_are_required(self):
        design=load_design()
        for key,values in (('detector_jitter_rms_s',(None,-1,True,float('inf'))),
                           ('holdover_bits',(None,0,-1,True,1.5))):
            for value in values:
                architecture=design.architecture
                if value is None:del architecture['blocks']['cdr']['parameters'][key]
                else:architecture['blocks']['cdr']['parameters'][key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)

    def test_ctle_transfer_is_required_and_valid_before_model_construction(self):
        design=load_design()
        for key in ('dc_gain','zero_s','pole_s'):
            for value in (None,0,-1,True,float('nan')):
                architecture=design.architecture
                if value is None:del architecture['blocks']['ctle']['parameters'][key]
                else:architecture['blocks']['ctle']['parameters'][key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)
        architecture=design.architecture
        architecture['blocks']['ctle']['parameters']['zero_s']=architecture['blocks']['ctle']['parameters']['pole_s']
        with self.assertRaisesRegex(ValueError,'must exceed'):
            DesignDefinition.from_documents(design.contract,architecture)

    def test_cdr_supply_delay_is_required_and_physically_bounded(self):
        design=load_design()
        for key in ('supply_sensitivity_ps_per_mv','delay_pole_hz'):
            for value in (None,-1,True,float('nan'))+( (0,) if key=='delay_pole_hz' else () ):
                architecture=design.architecture
                if value is None:del architecture['blocks']['cdr']['parameters'][key]
                else:architecture['blocks']['cdr']['parameters'][key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)

    def test_cdr_supply_delay_snapshot_reaches_wired_rx(self):
        import cmath
        from baseline_envelope import configured_environment,wired_shared_impairment
        design=load_design()
        variant=design.hypothetical(reason='CDR supply rejection uncertainty',changes={
            'blocks.cdr.parameters.supply_sensitivity_ps_per_mv':.2,
            'blocks.cdr.parameters.delay_pole_hz':5e8})
        outputs=[]
        for snapshot in (design,variant):
            environment=configured_environment(snapshot.configure(engine='wire',direction='duplex',
                reference_hz=2.5e9,host_divider=8))
            # A single independent injected rail tone isolates the transfer law.
            environment['host_spectrum']['tones']=[dict(frequency_hz=5e8,
                clock_rail_voltage_peak_v=.01,voltage_phase_rad=.3)]
            result=wired_shared_impairment(environment)['delay_tones'][0]
            outputs.append(result)
            missing=dict(environment);del missing['cdr_supply_delay_parameters']
            with self.assertRaisesRegex(ValueError,'missing CDR'):
                wired_shared_impairment(missing)
        nominal=design.architecture['blocks']['cdr']['parameters']
        expected=[.01*nominal['supply_sensitivity_ps_per_mv']*1e-9/(1+1j*5e8/nominal['delay_pole_hz']),2e-12/(1+1j)]
        for result,h in zip(outputs,expected):
            self.assertAlmostEqual(result['delay_peak_s']/1e-12,abs(h)/1e-12)
            self.assertAlmostEqual(result['delay_phase_rad'],.3+cmath.phase(h))
        self.assertNotEqual(outputs[0],outputs[1])
        gain_variant=design.hypothetical(reason='Independent wired gain-law sensitivity',changes={
            'model_assumptions.wired_supply_gain.parameters.reference_voltage_v':3.0})
        changed=configured_environment(gain_variant.configure(engine='wire',direction='duplex',
            reference_hz=2.5e9,host_divider=8))
        self.assertEqual(changed['board_source_v'],3.3)
        rail=changed['ledger']['local_payload_clock_core_rail_v']
        self.assertAlmostEqual(wired_shared_impairment(changed)['signal_scale'],rail/3.0)
        del changed['wired_supply_gain_parameters']
        with self.assertRaisesRegex(ValueError,'missing gain reference'):
            wired_shared_impairment(changed)
        for value in (None,0.,-1.,True,float('nan')):
            architecture=design.architecture
            parameters=architecture['model_assumptions']['wired_supply_gain']['parameters']
            if value is None:del parameters['reference_voltage_v']
            else:parameters['reference_voltage_v']=value
            with self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)

        from selected_rf import receive_frontend,receive_supply_reference
        import numpy as np
        rf_design=design.hypothetical(reason='RF gain reference sensitivity',changes={
            'model_assumptions.rf_receive_supply.parameters.gain_reference_v':3.0})
        rf_env=configured_environment(rf_design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=39))
        voltage=receive_supply_reference(rf_env,'gain_reference_v')
        args=(np.ones(4,complex),np.arange(4)/1e8,np.full(4,3.3),np.zeros(4))
        base,_=receive_frontend(*args,sample_hz=1e8,blocker_dbm=None)
        changed,_=receive_frontend(*args,sample_hz=1e8,blocker_dbm=None,gain_reference_v=voltage)
        np.testing.assert_allclose(changed,base*1.1,rtol=1e-14)
        self.assertEqual(receive_supply_reference(rf_env,'headroom_reference_v'),3.3)
        del rf_env['rf_receive_supply_parameters']
        with self.assertRaisesRegex(ValueError,'missing supply references'):
            receive_supply_reference(rf_env,'gain_reference_v')
        # Removing one identity marker must not turn an intended-chip input
        # into a primitive fixture with the legacy voltage reference.
        for marker in ('design_provenance','inventory_current_report','resolved_configuration'):
            with self.subTest(marker=marker),self.assertRaisesRegex(ValueError,'missing supply references'):
                receive_supply_reference({marker:rf_env[marker]},'gain_reference_v')
        self.assertEqual(receive_supply_reference({},'gain_reference_v'),3.3)

    def test_pad_inventory_uses_supplied_snapshot_without_reload(self):
        from check_contract import pad_behavioral_inventory
        from unittest.mock import patch
        design=load_design()
        with patch('design_definition.load_design',side_effect=AssertionError('Unexpected reload')):
            result=pad_behavioral_inventory(design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['wired_odd_mode_capacitance_f_per_leg'],
            design.architecture['blocks']['wirepad']['parameters']['capacitance_f_per_leg'])

    def test_pga_response_is_required_and_positive(self):
        design=load_design()
        for name in ('pga_i','pga_q'):
            for value in (None,0,-1,True,float('inf')):
                architecture=design.architecture
                parameters=architecture['blocks'][name]['parameters']
                if value is None:del parameters['gain_response_tau_s']
                else:parameters['gain_response_tau_s']=value
                with self.subTest(name=name,value=value), self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)

    def test_missing_and_invalid_shared_transport_allocations_fail_at_load(self):
        baseline=load_design()
        for key in ('ingress_bits_per_source','egress_bits_per_source'):
            for value in (None,0,-1,1.5,True):
                contract=baseline.contract
                if value is None:del contract['transport']['scheduling'][key]
                else:contract['transport']['scheduling'][key]=value
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    DesignDefinition.from_documents(contract,baseline.architecture)
        for value in (None,'',False):
            contract=baseline.contract
            if value is None:del contract['transport']['scheduling']['fifo_budget_status']
            else:contract['transport']['scheduling']['fifo_budget_status']=value
            with self.subTest(status=value), self.assertRaises(ValueError):
                DesignDefinition.from_documents(contract,baseline.architecture)
        for value in (0,-1,True):
            contract=baseline.contract
            contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=value
            with self.subTest(startup=value), self.assertRaises(ValueError):
                DesignDefinition.from_documents(contract,baseline.architecture)


    def test_fingerprint_tracks_content_not_json_format_or_key_order(self):
        design = load_design()
        reordered = DesignDefinition(json.dumps(design.contract, indent=4),
                                     json.dumps(dict(reversed(list(design.architecture.items())))))
        self.assertEqual(design.fingerprint, reordered.fingerprint)
        changed = design.architecture
        changed['blocks']['refbuf']['parameters']['output_r_ohm'] += 1
        self.assertNotEqual(design.fingerprint,
                            DesignDefinition.from_documents(design.contract, changed).fingerprint)

    def test_current_totals_do_not_depend_on_block_order(self):
        from rf_quality_budget import current_allocation
        architecture = load_design().architecture
        reordered = dict(architecture, blocks=dict(reversed(list(architecture['blocks'].items()))))
        for mode in architecture['operating_modes']:
            self.assertEqual(current_allocation(architecture, mode),
                             current_allocation(reordered, mode))

    def test_snapshot_does_not_share_mutable_test_inputs(self):
        design = load_design()
        architecture = design.architecture
        snapshot = DesignDefinition.from_documents(design.contract, architecture)
        before = snapshot.fingerprint
        architecture['blocks']['pga_i']['parameters']['gain_db'].append(54)
        snapshot.architecture['blocks']['pga_i']['parameters']['gain_db'].append(60)
        self.assertEqual(snapshot.fingerprint, before)
        self.assertNotIn(54, snapshot.architecture['blocks']['pga_i']['parameters']['gain_db'])
        self.assertNotIn(60, snapshot.architecture['blocks']['pga_i']['parameters']['gain_db'])

    def test_missing_reference_and_nonfinite_data_fail_at_load(self):
        design = load_design()
        architecture = design.architecture
        del architecture['blocks']['refbuf']['parameters']['quiescent_current_a']
        with self.assertRaisesRegex(ValueError, 'quiescent_current_a'):
            DesignDefinition.from_documents(design.contract, architecture)
        architecture = design.architecture
        architecture['blocks']['refbuf']['parameters']['output_r_ohm'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite JSON'):
            DesignDefinition.from_documents(design.contract, architecture)

    def test_integrated_environment_records_the_snapshot_it_used(self):
        from baseline_envelope import inventory_environment
        design = load_design()
        changed = design.architecture
        changed['blocks']['refbuf']['parameters']['output_r_ohm'] = 70.
        snapshot = DesignDefinition.from_documents(design.contract, changed)
        e = inventory_environment(snapshot.contract, snapshot.architecture, 'rf', 2.4e9, 150e6)
        self.assertEqual(e['design_provenance'], snapshot.provenance())
        self.assertEqual(e['converter_parameters']['reference_r_ohm'], 70.)
        self.assertNotEqual(e['design_provenance']['design_fingerprint'], design.fingerprint)


class ResolvedConfigurationTests(unittest.TestCase):
    def test_stable_rf_host_tracks_configuration_across_real_hop(self):
        from dataclasses import replace
        from timing_services import WarmHop
        from baseline_envelope import configured_environment
        d=load_design()
        config=d.configure(engine='rf',direction='rx',reference_hz=2.402e9,
            sample_divider=64,pga_gain_db=39,host_clock_source='h2d_divided')
        next_config=replace(config,reference_hz=2.480e9)
        self.assertNotEqual(config.sample_hz,next_config.sample_hz)
        self.assertEqual(config.host_word_hz,next_config.host_word_hz)
        for c in (config,next_config):
            e=configured_environment(c)
            self.assertEqual(e['host_spectrum']['d2h_word_hz'],c.host_word_hz)
            self.assertEqual(e['transport_parameters']['d2h_word_hz'],c.host_word_hz)
            self.assertEqual(e['clock_domains']['converter_hz'],c.sample_hz)
        h=WarmHop.from_configuration(config,7)
        with self.assertRaisesRegex(ValueError,'preserve'):
            h.begin_configuration(replace(next_config,host_clock_source='reference_divider'),
                context_loaded=True,muted=True,queues_discarded=True)
        h.begin_configuration(next_config,context_loaded=True,muted=True,queues_discarded=True)
        self.assertFalse(h.observe(35e-6,source_qualified=True))
        self.assertTrue(h.observe(49e-6,source_qualified=True,samples_flushed=True,
            gain_settled=True,epoch_ack=True,prefilled=True))
        h.launch(50e-6,8)
        self.assertIs(h.configuration,next_config)
        with self.assertRaisesRegex(ValueError,'stable'):
            WarmHop.from_configuration(replace(config,host_clock_source='reference_divider'),7)

    def test_fractional_forwarded_clock_resolves_pll_and_transport(self):
        from baseline_envelope import configured_environment
        d=load_design()
        for pixel,host_divider in ((74.25e6,4),(148.5e6,8)):
            for scale in (1.,1.001):
                c=d.configure(engine='wire',direction='tx',reference_hz=pixel/scale,
                    clock_source='forwarded_word',host_divider=host_divider)
                self.assertAlmostEqual(c.line_rate_bps/(10*pixel/scale),1.,places=14)
                self.assertEqual(c.wire_output_divider,2 if pixel<100e6 else 1)
                self.assertAlmostEqual(c.host_word_hz,c.line_rate_bps/host_divider)
                e=configured_environment(c)
                self.assertEqual(e['clock_domains'],c.clock_domains)
                self.assertEqual(e['transport_parameters']['d2h_word_hz'],c.host_word_hz)
                self.assertTrue(c.record()['clock_domains']['synthesis_required'])
                from baseline_envelope import reference_payload_environment
                with self.assertRaisesRegex(ValueError,'not the line clock'):
                    reference_payload_environment(e,dict(link_r_ohm=1e-5),False)

        with self.assertRaisesRegex(ValueError,'conflicts'):
            d.configure(engine='wire',direction='tx',reference_hz=74.25e6,
                clock_source='forwarded_word',host_divider=4,line_rate_bps=1.485e9)

    def test_rf_example_resolves_rates_and_ownership(self):
        design = load_design()
        config = design.configure(engine='rf', direction='rx', reference_hz=2.426e9,
                                  sample_divider=64, pga_gain_db=39)
        self.assertEqual(config.sample_hz, 37_906_250.)
        self.assertEqual(config.host_word_hz, 151_625_000.)
        self.assertEqual(config.inventory_mode, 'rf_rx')
        self.assertEqual(config.record()['design_fingerprint'], design.fingerprint)

    def test_hypothetical_gain_and_unsupported_divider_are_not_settings(self):
        design = load_design()
        base = dict(engine='rf', direction='rx', reference_hz=2.426e9,
                    sample_divider=64, pga_gain_db=39)
        for change in ({'lna_gain_db':21},{'lna_gain_db':True},{'pga_gain_db':54}, {'pga_gain_db':None}, {'sample_divider':63},
                       {'sample_divider':64.0}, {'reference_hz':float('nan')},
                       {'direction':'duplex'}, {'host_divider':8}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                design.configure(**dict(base, **change))

    def test_converter_limit_is_loaded_and_applies_to_both_lanes(self):
        design = load_design()
        architecture = design.architecture
        architecture['blocks']['adc_q']['parameters']['sample_rate_max_hz'] = 30e6
        changed = DesignDefinition.from_documents(design.contract, architecture)
        with self.assertRaisesRegex(ValueError, 'converter allocation'):
            changed.configure(engine='rf', direction='rx', reference_hz=2.426e9,
                              sample_divider=64, pga_gain_db=39)
        slow = changed.configure(engine='rf', direction='rx', reference_hz=2.426e9,
                                 sample_divider=128, pga_gain_db=39)
        self.assertEqual(slow.sample_hz, 18_953_125.)

    def test_transmit_has_its_own_mode_and_cannot_select_rx_pga(self):
        design = load_design()
        config = design.configure(engine='rf', direction='tx', reference_hz=2.4e9,
                                  sample_divider=64)
        self.assertEqual(config.inventory_mode, 'rf_tx')
        from check_contract import verify_reported_configuration
        import copy
        # Independent exhaustive nearest-code oracle, not the production resolver.
        driver=design.architecture['blocks']['rfdriver']['parameters']
        low,high=driver['gain_range'];levels=2**driver['gain_bits']-1
        values=[low+i*(high-low)/levels for i in range(levels+1)]
        for requested in (low,4.5,5.36,5.72,high):
            selected=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,
                sample_divider=64,tx_gain=requested)
            nearest=min(range(len(values)),key=lambda code:abs(values[code]-requested))
            self.assertEqual(selected.tx_gain_code,nearest)
            self.assertAlmostEqual(selected.resolved_tx_gain,values[nearest])
            self.assertEqual(verify_reported_configuration(design,selected.record()),selected)
            changed=copy.deepcopy(selected.record());changed['tx_gain_code']^=1
            with self.assertRaises(ValueError):verify_reported_configuration(design,changed)
        for gain in (True,float('nan'),0.,7.):
            with self.assertRaises(ValueError):
                design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64,tx_gain=gain)
        with self.assertRaisesRegex(ValueError,'TX gain supplied'):
            design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
                sample_divider=64,pga_gain_db=39,tx_gain=4.5)

        with self.assertRaisesRegex(ValueError, 'RX PGA'):
            design.configure(engine='rf', direction='tx', reference_hz=2.4e9,
                             sample_divider=64, pga_gain_db=39)

        self.assertEqual(config.h2d_clock_hz,156.25e6)
        self.assertEqual(config.control_hz,39.0625e6)
        direct=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')
        self.assertEqual(direct.h2d_clock_hz,100e6)
        self.assertEqual(direct.control_hz,25e6)
        from baseline_envelope import configured_environment
        from design_definition import validate_transport_binding
        environment=configured_environment(direct)
        self.assertEqual(environment['control_hz'],25e6)
        self.assertEqual(validate_transport_binding(environment)['control_hz'],25e6)
        changed=design.hypothetical(reason='Scheduler divider propagation control',changes={
            'control_semantics.scheduler_clock_divider':8})
        slower=changed.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64)
        self.assertEqual(configured_environment(slower)['control_hz'],19.53125e6)
        from selected_lifecycle import selected_turnaround_requirement
        budget=selected_turnaround_requirement(changed.contract,design=changed)
        self.assertEqual(budget['control_hz'],19.53125e6)
        self.assertEqual(budget['resolved_configurations']['rx']['control_hz'],19.53125e6)
        environment['control_hz']=12.5e6
        with self.assertRaisesRegex(ValueError,'Control clock conflicts'):
            validate_transport_binding(environment)
        for value in (None,0,True,4.0):
            architecture=design.architecture
            if value is None:del architecture['control_semantics']['scheduler_clock_divider']
            else:architecture['control_semantics']['scheduler_clock_divider']=value
            with self.assertRaises(ValueError):DesignDefinition.from_documents(design.contract,architecture)

    def test_wired_requires_explicit_host_divider_and_no_rf_controls(self):
        design = load_design()
        base = dict(engine='wire', direction='duplex', reference_hz=2.5e9, host_divider=8)
        config = design.configure(**base)
        self.assertEqual(config.host_word_hz, 312.5e6)
        self.assertEqual(config.inventory_mode, 'wired')
        for change in ({'host_divider':None}, {'pga_gain_db':39}, {'line_rate_bps':1.25e9},
                       {'sample_divider':64}, {'wired_pad_path':'unknown'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                design.configure(**dict(base, **change))


class ScenarioBindingTests(unittest.TestCase):
    def test_declared_package_and_load_changes_reach_electrical_model(self):
        from design_definition import Scenario
        from baseline_envelope import configured_environment
        design = load_design()
        config = design.configure(engine='rf', direction='rx', reference_hz=2.426e9,
                                  sample_divider=64, pga_gain_db=39)
        nominal = configured_environment(config)
        scenario = Scenario().override(package_return_inductance_h=2e-9,
                                       host_output_load_f=12e-12,
                                       reason='Adverse package and board loading')
        adverse = configured_environment(config, scenario)
        self.assertEqual(nominal['network']['return_l_h'], .25e-9)
        self.assertEqual(adverse['network']['return_l_h'], 2e-9)
        self.assertEqual(adverse['host_spectrum']['output_cap_f'], 12e-12)
        self.assertEqual(nominal['host_spectrum']['output_cap_f'], 6e-12)
        self.assertEqual(adverse['resolved_configuration'], config.record())
        self.assertEqual(adverse['scenario_overrides'], scenario.record())
        self.assertEqual(adverse['design_provenance'], nominal['design_provenance'])
        self.assertNotEqual(adverse['host_spectrum']['tones'], nominal['host_spectrum']['tones'])
        self.assertEqual(Scenario().record(), [])

    def test_uncertainty_cannot_smuggle_in_hardware_settings_or_unapplied_inputs(self):
        from design_definition import Scenario
        for parameters in ({'pga_gain_db': 54}, {'temperature_c': 25},
                           {'host_output_load_f': float('nan')},
                           {'package_return_inductance_h': -1}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                Scenario().override(reason='Explicit test', **parameters)
        with self.assertRaises(ValueError):
            Scenario().override(reason='', package_return_inductance_h=2e-9)

    def test_snapshot_package_assumption_is_consumed_without_reloading_files(self):
        from baseline_envelope import configured_environment
        design = load_design()
        architecture = design.architecture
        architecture['blocks']['power']['parameters']['shared_return_l_h'] = .75e-9
        alternative = DesignDefinition.from_documents(design.contract, architecture)
        config = alternative.configure(engine='wire', direction='duplex',
                                       reference_hz=2.5e9, host_divider=8)
        environment = configured_environment(config)
        self.assertEqual(environment['network']['return_l_h'], .75e-9)
        self.assertEqual(environment['design_provenance'], alternative.provenance())


class CalibrationObservationSnapshotTests(unittest.TestCase):
    def test_shared_comparator_noise_rejects_invalid_values_but_allows_zero(self):
        from calibration_observation_budget import observation_budget
        design=load_design()
        key='model_assumptions.paired_sar.parameters.comparator_noise_rms_v'
        for invalid in (-.001,True,False,'quiet'):
            with self.subTest(noise=invalid),self.assertRaisesRegex(ValueError,'comparator RMS noise'):
                design.hypothetical(reason='Malformed comparator-noise fixture',changes={key:invalid})
        quiet=design.hypothetical(reason='Explicit noiseless comparison',changes={key:0.})
        result=observation_budget(quiet)
        self.assertEqual(result['noise_only_coverage_of_300uv_bound'],1.)
        for row in result['rows']:
            self.assertEqual(row['noise_rms_v'],0.)
            self.assertEqual(row['minimum_samples_zero_residual_optimistic'],1)
            for estimate in row['estimates']:
                self.assertEqual(estimate['optimistic_half_width_v'],result['quantization_half_lsb_v'])

    def test_noise_comes_from_snapshot_and_tolerance_is_a_diagnostic_input(self):
        from calibration_observation_budget import observation_budget
        from statistics import NormalDist
        from unittest.mock import patch
        import math
        design=load_design().hypothetical(reason='Comparator observation-noise experiment',changes={
            'model_assumptions.paired_sar.parameters.comparator_noise_rms_v':.002})
        with patch('calibration_observation_budget.load_design',side_effect=AssertionError('Unexpected reload')):
            result=observation_budget(design,tolerance_v=.003)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['diagnostic_assumptions']['residual_tolerance_v'],.003)
        bits=design.architecture['blocks']['adc_i']['parameters']['native_bits']
        half_lsb=2.**(-bits)
        for row in result['rows']:
            z=NormalDist().inv_cdf((1+row['confidence'])/2)
            for estimate in row['estimates']:
                expected=z*.002/math.sqrt(estimate['samples'])+half_lsb
                self.assertAlmostEqual(estimate['optimistic_half_width_v'],expected,places=15)
                self.assertAlmostEqual(estimate['remaining_residual_allowance_v'],max(0.,.003-expected),places=15)
        for invalid in (True,0.,-1.,float('nan'),float('inf'),'small'):
            with self.subTest(tolerance=invalid),self.assertRaisesRegex(ValueError,'diagnostic residual tolerance'):
                observation_budget(design,tolerance_v=invalid)


class ReceiverSnapshotTests(unittest.TestCase):
    def test_shared_rx_gain_rejection_preserves_blocker_and_rail_constraints(self):
        import numpy as np
        from baseline_envelope import configured_environment
        from selected_rf import receive_frontend,receive_gain_elasticity
        d=load_design()
        env=configured_environment(d.configure(engine='rf',direction='rx',reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        elasticity=receive_gain_elasticity(env)
        rate=100e6;t=np.arange(10000)/rate
        rail=3.3+.06*np.cos(2*np.pi*10e6*t)
        def spectrum(e):
            v,_=receive_frontend(np.zeros(len(t)),t,rail,np.zeros(len(t)),sample_hz=rate,
                blocker_dbm=-50.,blocker_offset_hz=12e6,gain_supply_elasticity=e)
            return np.abs(np.fft.fft(v))/len(v)
        selected=spectrum(elasticity);control=spectrum(1.)
        # A 12 MHz blocker and 10 MHz supply modulation produce a 2 MHz spur.
        self.assertAlmostEqual(selected[200]/control[200],elasticity,places=10)
        self.assertAlmostEqual(selected[1200]/control[1200],1.,places=10)
        for e in (-1.,float('nan'),True):
            with self.assertRaises(ValueError):spectrum(e)
        broken=dict(env);broken['rf_receive_supply_parameters']=dict(env['rf_receive_supply_parameters'])
        del broken['rf_receive_supply_parameters']['gain_supply_elasticity']
        with self.assertRaises(KeyError):receive_gain_elasticity(broken)
        with self.assertRaises(ValueError):
            receive_frontend(np.ones(2),np.arange(2)/rate,np.zeros(2),np.zeros(2),sample_hz=rate,
                gain_supply_elasticity=0.)

    def test_wired_recovery_does_not_ignore_or_partly_apply_rail_stimuli(self):
        from behavioral import BehavioralChip,Assumptions
        from selected_lifecycle import loaded_wired_recovery
        from unittest.mock import patch
        design=load_design()
        for voltage,delay in ((lambda t:3.,None),(None,lambda t:0.),(3.,lambda t:0.),(lambda t:3.,0.)):
            chip=BehavioralChip(Assumptions(startup_s=0.))
            original=chip.a;before=(chip.state,chip.time,chip.epoch)
            with self.subTest(voltage=voltage,delay=delay),patch('wired_envelope.physical_receiver') as receiver:
                with self.assertRaisesRegex(ValueError,'Shared rail voltage and delay'):
                    loaded_wired_recovery(design.contract,design=design,chip=chip,
                                          rail_voltage=voltage,rail_delay=delay)
                receiver.assert_not_called()
            self.assertIs(chip.a,original)
            self.assertEqual((chip.state,chip.time,chip.epoch),before)

    def test_wired_recovery_rejects_running_chip_without_mutating_assumptions(self):
        from behavioral import BehavioralChip,Assumptions
        from selected_lifecycle import loaded_wired_recovery
        from unittest.mock import patch
        design=load_design()
        assumptions=Assumptions(startup_s=0.,h2d_clock_scale=.9)
        chip=BehavioralChip(assumptions)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
        before=(chip.state,chip.time,chip.epoch)
        with patch('wired_envelope.physical_receiver') as receiver:
            with self.assertRaisesRegex(ValueError,'requires a stopped chip'):
                loaded_wired_recovery(design.contract,design=design,chip=chip)
            receiver.assert_not_called()
        self.assertIs(chip.a,assumptions)
        self.assertEqual((chip.state,chip.time,chip.epoch),before)

    def test_rf_entry_points_reject_a_consistent_wired_snapshot(self):
        from baseline_envelope import configured_environment
        from selected_rf import wideband_receive,wideband_transmit
        from wifi_client_exchange import SharedRFPath
        from ble_packet import joined_scan_request,transmitted_scan_response
        from unittest.mock import patch
        design=load_design()
        config=design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)
        environment=configured_environment(config)
        callers=(lambda:wideband_receive(environment),lambda:wideband_transmit(environment),
                 lambda:SharedRFPath(environment=environment),
                 lambda:joined_scan_request(environment,design.contract),
                 lambda:transmitted_scan_response({},environment,design.contract))
        with patch('selected_rf.selected_filter_cutoff') as filter_solver:
            for call in callers:
                with self.subTest(call=call),self.assertRaisesRegex(ValueError,'resolved RF engine'):
                    call()
            filter_solver.assert_not_called()

    def test_inventory_never_reloads_or_falls_back_to_primitive_converter(self):
        from baseline_envelope import receiver_inventory_options
        from converter_dynamics import parameters_from_inventory
        from unittest.mock import patch
        design=load_design()
        with patch('design_definition.load_design',side_effect=AssertionError('Unexpected reload')):
            with self.assertRaisesRegex(ValueError,'explicit architecture'):
                receiver_inventory_options({})
            options=receiver_inventory_options({},architecture=design.architecture)
        self.assertEqual(options['sar_parameters'],parameters_from_inventory(design.architecture))
        environment={'receiver_parameters':{name:design.architecture['blocks'][name]['parameters']
            for name in ('adc_i','adc_q','pga_i','pga_q','lna')}}
        with self.assertRaisesRegex(ValueError,'converter parameters'):
            receiver_inventory_options(environment)

    def test_receiver_parameters_use_the_original_snapshot(self):
        from baseline_envelope import configured_environment, receiver_inventory_options
        design = load_design()
        architecture = design.architecture
        architecture['blocks']['lna']['parameters']['noise_figure_db'] = 7.25
        design = DesignDefinition.from_documents(design.contract, architecture)
        config = design.configure(engine='rf', direction='rx', reference_hz=2.426e9,
                                  sample_divider=128, pga_gain_db=39)
        environment = configured_environment(config)
        self.assertEqual(receiver_inventory_options(environment)['noise_figure_db'], 7.25)
        self.assertEqual(environment['resolved_configuration']['sample_hz'], 18_953_125.)

    def test_configured_receiver_rejects_implicit_gain_experiments(self):
        from baseline_envelope import configured_environment, coupled_wideband_feedback
        config = load_design().configure(engine='rf', direction='rx', reference_hz=2.426e9,
                                         sample_divider=64, pga_gain_db=39)
        with self.assertRaisesRegex(ValueError, 'Gain override'):
            coupled_wideband_feedback(configured_environment(config), gain_db=54.)


class HypotheticalCircuitTests(unittest.TestCase):
    def test_hypothetical_gain_is_separate_and_preserves_provenance(self):
        from baseline_envelope import configured_environment, receiver_inventory_options
        design=load_design()
        settings=dict(engine='rf',direction='rx',reference_hz=2.426e9,
                      sample_divider=64,pga_gain_db=54)
        with self.assertRaises(ValueError):design.configure(**settings)
        codes=design.architecture['blocks']['pga_i']['parameters']['gain_db']+[54]
        hypothetical=design.hypothetical(reason='Explore extra PGA stage requirement',changes={
            'blocks.pga_i.parameters.gain_db':codes,
            'blocks.pga_q.parameters.gain_db':codes})
        config=hypothetical.configure(**settings)
        environment=configured_environment(config)
        self.assertIn(54,receiver_inventory_options(environment)['gain_codes_db'])
        record=environment['design_provenance']
        self.assertNotEqual(record['design_fingerprint'],design.fingerprint)
        self.assertEqual(record['circuit_experiments'][0]['parent_design_fingerprint'],design.fingerprint)
        self.assertEqual(record['circuit_experiments'][0]['reason'],'Explore extra PGA stage requirement')
        self.assertEqual(design.provenance()['circuit_experiments'],[])
        with self.assertRaises(ValueError):design.configure(**settings)
        codes.append(60)
        self.assertNotIn(60,hypothetical.architecture['blocks']['pga_i']['parameters']['gain_db'])

    def test_unknown_paths_and_unexplained_circuit_changes_fail(self):
        design=load_design()
        for reason,changes in (('',{'blocks.pga_i.parameters.gain_db':[54]}),
                               ('Experiment',{'blocks.pga_i.parameters.typo':1}),
                               ('Experiment',{'operating_modes':[]}),
                               ('Experiment',{})):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                design.hypothetical(reason=reason,changes=changes)


class PacketFactoryTests(unittest.TestCase):
    def test_factory_inspection_cannot_rebind_the_constructed_model(self):
        from unittest.mock import patch
        from design_definition import Scenario
        from baseline_envelope import build_model
        config=load_design().configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                       sample_divider=64,pga_gain_db=39)
        scenario=Scenario(wanted_dbm=-80,blocker_dbm=-40,reference_peak_v=.5)
        def accept(seed,*args,**kwargs):return seed,{'status':'accepted'}
        with patch('baseline_envelope.reference_payload_environment',side_effect=accept):
            model=build_model(config,scenario)
        for name,value in (('config',None),('scenario',Scenario()),('environment',{}),('clock',{}),('seed',{})):
            with self.subTest(property=name),self.assertRaises(AttributeError):setattr(model,name,value)
        model.environment['receiver_parameters']['lna']['noise_figure_db']=99.
        model.seed['resolved_configuration']['pga_gain_db']=54.
        model.clock['status']='rejected'
        with patch('wideband_packet.run_case',return_value={'fixture_result':True}) as run:
            result=model.receive(b'hello')
        self.assertEqual(run.call_args.args[0]['receiver_parameters']['lna']['noise_figure_db'],
                         config.design.architecture['blocks']['lna']['parameters']['noise_figure_db'])
        self.assertEqual(run.call_args.kwargs['wanted_dbm'],-80)
        self.assertEqual(run.call_args.kwargs['packet'],b'hello')
        self.assertEqual(result['resolved_configuration'],config.record())
        self.assertEqual(result['clock']['status'],'accepted')
        self.assertEqual(result['status'],'evaluated')

    def test_feedback_wrappers_preserve_owned_result_context(self):
        from copy import deepcopy
        from unittest.mock import patch
        import numpy as np
        from baseline_envelope import configured_environment,coupled_scan_request,coupled_wideband_feedback
        design=load_design();config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=64,pga_gain_db=39)
        environment=configured_environment(config)
        environment['reference_return_options']={'link_r_ohm':1e-5}
        response={'times_s':np.array([0.,1.]),'input_v':np.zeros(2)}
        with patch('baseline_envelope.reference_feedback_response',return_value=(response,{})),              patch('baseline_envelope.response_change',return_value=(0.,0.,True)),              patch('baseline_envelope.joined_scan_request',return_value={'correct_request':True}),              patch('baseline_envelope.wideband_receive',return_value={'coupled_load_clock':{}}):
            narrow,_=coupled_scan_request(environment,design.contract,rx_options={},stimulus={})
            wide=coupled_wideband_feedback(environment,oversample=256)
        expected=deepcopy(environment['resolved_configuration'])
        for result in (narrow,wide):
            result['resolved_configuration']['reference_hz']=1.
            result['design_provenance']['documents'].clear()
            result['operating_conditions']['temperature_k']=0.
            self.assertEqual(environment['resolved_configuration'],expected)
            self.assertEqual(environment['design_provenance'],design.provenance())
            self.assertGreater(environment['operating_conditions']['temperature_k'],0.)

    def test_wired_transport_result_does_not_alias_configuration(self):
        from baseline_envelope import configured_environment,wired_transmit_transport
        design=load_design();config=design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)
        environment=configured_environment(config)
        result,_=wired_transmit_transport(environment,frames=1)
        result['resolved_configuration']['reference_hz']=1.
        result['design_provenance']['documents'].clear()
        self.assertEqual(environment['resolved_configuration'],config.record())
        self.assertEqual(environment['design_provenance'],design.provenance())

    def test_clock_rejection_preserves_configuration_and_does_not_decode(self):
        from unittest.mock import patch
        from design_definition import Scenario
        from baseline_envelope import build_model
        config=load_design().configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                       sample_divider=64,pga_gain_db=39)
        scenario=Scenario(wanted_dbm=-80,blocker_dbm=-40,reference_peak_v=.5).override(
            package_return_inductance_h=2e-9,reason='Adverse package')
        with patch('baseline_envelope.reference_payload_environment',return_value=(None,{'status':'rejected'})), \
             patch('wideband_packet.run_case') as decoder:
            model=build_model(config,scenario)
            result=model.receive(b'hello')
        decoder.assert_not_called()
        self.assertEqual(result['status'],'clock_rejected')
        self.assertEqual(result['stimuli']['wanted_dbm'],-80)
        self.assertEqual(result['scenario_overrides'][0]['reason'],'Adverse package')
        self.assertEqual(result['resolved_configuration'],config.record())
        original_temperature=result['operating_conditions']['temperature_k']
        result['clock']['status']='report-only mutation'
        result['operating_conditions']['temperature_k']=0.
        next_result=model.receive(b'hello')
        self.assertEqual(next_result['clock']['status'],'rejected')
        self.assertEqual(next_result['operating_conditions']['temperature_k'],original_temperature)
        self.assertEqual(model.clock['status'],'rejected')
        self.assertEqual(model.seed['operating_conditions']['temperature_k'],original_temperature)

    def test_packet_stimulus_uses_actual_supplied_bytes(self):
        from wideband_packet import source,receive
        packet=b'actual user payload'
        wave,truth,_=source(0,payload_bytes=len(packet),packet=packet)
        decoded,_=receive(wave.samples,payload_bytes=len(packet))
        self.assertEqual(truth,packet)
        self.assertEqual(bytes.fromhex(decoded['payload_hex']),packet)
        self.assertTrue(decoded['crc_ok'])


class SharedNetworkTests(unittest.TestCase):
    def test_changed_feed_resistance_reaches_dc_and_ac_network(self):
        from baseline_envelope import configured_environment
        design=load_design()
        settings=dict(engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=64,pga_gain_db=39)
        nominal=configured_environment(design.configure(**settings))
        changed=design.hypothetical(reason='Board feed resistance sensitivity',changes={
            'blocks.power.parameters.reduced_pdn_model.network.feed_r':.2})
        adverse=configured_environment(changed.configure(**settings))
        self.assertEqual(adverse['network']['network']['feed_r'],.2)
        # Independent Ohm-law prediction for the added 0.1 ohm feed resistance.
        current=nominal['ledger']['total_chip_supply_current_a']
        self.assertAlmostEqual(nominal['ledger']['board_supply_v']-adverse['ledger']['board_supply_v'],current*.1)
        self.assertNotEqual(nominal['host_spectrum']['tones'],adverse['host_spectrum']['tones'])
        self.assertNotEqual(nominal['design_provenance'],adverse['design_provenance'])

    def test_missing_integrated_network_value_fails_at_load(self):
        design=load_design();architecture=design.architecture
        del architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['die_c']
        with self.assertRaisesRegex(ValueError,'die_c'):
            DesignDefinition.from_documents(design.contract,architecture)


class LoadedClockSnapshotTests(unittest.TestCase):
    def test_noise_assumptions_survive_loaded_clock_composition(self):
        from baseline_envelope import configured_environment,reference_payload_environment
        design=load_design().hypothetical(reason='Clock noise sensitivity',changes={
            'blocks.refinput.parameters.receiver_noise_v':90e-6,
            'blocks.clocktree.parameters.downstream_stage_rms_s':25e-15})
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                sample_divider=64,pga_gain_db=39)
        seed=configured_environment(config)
        self.assertEqual(seed['external_clock_input']['receiver_noise_v'],90e-6)
        loaded,report=reference_payload_environment(seed,{'link_r_ohm':1e-5},False,source_peak_v=.5)
        self.assertIsNotNone(loaded,report)
        self.assertAlmostEqual(loaded['external_clock_input']['receiver_noise_v'],2**.5*90e-6,places=14)
        self.assertEqual(loaded['external_clock_input']['downstream_stage_rms_s'],25e-15)


class ConverterOwnershipTests(unittest.TestCase):
    def test_receiver_paths_reject_foreign_sar_before_waveform_generation(self):
        from dataclasses import replace
        from unittest.mock import patch
        import baseline_envelope as b
        import selected_rf,ble_packet
        from converter_dynamics import tone_precision
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                sample_divider=64,pga_gain_db=39)
        environment=b.configured_environment(config)
        owned=b.environment_converter_parameters(environment)
        foreign=replace(owned,dac_tau_s=owned.dac_tau_s*2)
        paths=((lambda env,p:selected_rf.wideband_receive(env,sar_parameters=p),'selected_rf.he_source'),
               (lambda env,p:ble_packet.joined_scan_request(env,design.contract,sar_parameters=p),'ble_packet.gfsk'),
               (lambda env,p:tone_precision(env,p),'selected_rf.DeliveredClock'))
        for call,source in paths:
            with self.subTest(source=source),patch(source,side_effect=AssertionError('Waveform must not start')):
                with self.assertRaisesRegex(ValueError,'SAR parameters conflict.*dac_tau_s'):
                    call(environment,foreign)
                broken=dict(environment,converter_parameters=dict(environment['converter_parameters']))
                del broken['converter_parameters']['dac_tau_s']
                with self.assertRaisesRegex(ValueError,'complete converter parameters'):
                    call(broken,owned)

    def test_matching_hypothesis_and_temperature_reach_both_receivers(self):
        from unittest.mock import patch
        import baseline_envelope as b
        import selected_rf,ble_packet
        from converter_dynamics import tone_precision
        from converter_dynamics import SARParameters,validate_sar_binding
        from design_definition import Scenario
        variant=load_design().hypothetical(reason='Explicit slower converter circuit',changes={
            'model_assumptions.paired_sar.parameters.dac_tau_s':.6e-9})
        config=variant.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                 sample_divider=64,pga_gain_db=39)
        environment=b.configured_environment(config,Scenario(assumptions={'temperature_c':25.}))
        parameters=b.environment_converter_parameters(environment)
        self.assertEqual(parameters.dac_tau_s,.6e-9)
        self.assertEqual(parameters.temperature_k,298.15)
        for call,source in (
                (lambda:selected_rf.wideband_receive(environment,sar_parameters=parameters),'selected_rf.he_source'),
                (lambda:ble_packet.joined_scan_request(environment,variant.contract,sar_parameters=parameters),'ble_packet.gfsk'),
                (lambda:tone_precision(environment,parameters),'selected_rf.DeliveredClock')):
            with self.subTest(source=source),patch(source,side_effect=RuntimeError('Reached independent source')):
                with self.assertRaisesRegex(RuntimeError,'Reached independent source'):call()
        model=environment['comparator_parameters']
        validate_sar_binding(environment,parameters,comparator_model=model)
        with self.assertRaisesRegex(ValueError,'Comparator model conflicts'):
            validate_sar_binding(environment,parameters,comparator_model=dict(model,tau_s=100e-12))
        broken=dict(environment);del broken['comparator_parameters']
        with self.assertRaisesRegex(ValueError,'complete comparator parameters'):
            validate_sar_binding(broken,parameters,comparator_model=model)
        validate_sar_binding({},SARParameters(dac_tau_s=1e-9))
        validate_sar_binding(environment,None)  # Explicit assigned-ENOB mode remains available.
        import copy
        # Acceptance limits and result identity must be checked before any
        # expensive waveform work, not inferred from an optional fingerprint.
        with patch('selected_rf.DeliveredClock',side_effect=AssertionError('Waveform must not start')):
            for field in ('design_provenance','resolved_configuration','receiver_parameters'):
                damaged=copy.deepcopy(environment);del damaged[field]
                with self.subTest(missing=field),self.assertRaises(ValueError):
                    tone_precision(damaged,parameters)
            for value in (None,0.,-1.,True,float('nan')):
                damaged=copy.deepcopy(environment)
                if value is None:del damaged['receiver_parameters']['adc_i']['enob_target']
                else:damaged['receiver_parameters']['adc_i']['enob_target']=value
                with self.subTest(enob=value),self.assertRaisesRegex(ValueError,'ENOB targets'):
                    tone_precision(damaged,parameters)
        with self.assertRaisesRegex(ValueError,'converter clock feedback missing'):
            tone_precision(environment,parameters,shared_clock_feedback=True)

    def test_device_hypotheses_are_resolved_from_design(self):
        from converter_dynamics import parameters_from_inventory
        design=load_design();architecture=design.architecture
        architecture['model_assumptions']['paired_sar']['parameters']['dac_tau_s']=.45e-9
        architecture['blocks']['board']['parameters']['nominal_temperature_c']=25.
        p=parameters_from_inventory(architecture)
        self.assertEqual(p.dac_tau_s,.45e-9)
        self.assertEqual(p.temperature_k,298.15)

    def test_missing_or_duplicate_owner_cannot_fall_back_to_primitive_defaults(self):
        from converter_dynamics import parameters_from_inventory
        design=load_design();architecture=design.architecture
        del architecture['model_assumptions']['paired_sar']['parameters']['sample_resistance_ohm']
        with self.assertRaisesRegex(ValueError,'sample_resistance_ohm'):
            DesignDefinition.from_documents(design.contract,architecture)
        with self.assertRaisesRegex(ValueError,'every converter parameter'):
            parameters_from_inventory(architecture)
        architecture=design.architecture
        architecture['model_assumptions']['paired_sar']['parameters']['reference_cap_f']=1e-9
        with self.assertRaisesRegex(ValueError,'Duplicate ownership'):
            parameters_from_inventory(architecture)

    def test_frontend_thermal_noise_obeys_temperature_scaling(self):
        import numpy as np
        from selected_rf import receive_frontend
        t=np.arange(32)/20e6
        def noise(temperature):
            return receive_frontend(np.zeros(32),t,np.full(32,3.3),np.zeros(32),
                sample_hz=20e6,blocker_dbm=None,temperature_k=temperature,
                noise_rng=np.random.default_rng(7))[0]
        # Johnson-noise power is proportional to absolute temperature.
        self.assertAlmostEqual(float(np.vdot(noise(600),noise(600)).real /
                                     np.vdot(noise(300),noise(300)).real),2.)


class OperatingAssumptionTests(unittest.TestCase):
    def test_temperature_is_immutable_recorded_and_reaches_converter(self):
        from design_definition import Scenario
        from baseline_envelope import configured_environment,environment_converter_parameters
        values={'temperature_c':25}
        scenario=Scenario(assumptions=values)
        values['temperature_c']=32
        scenario=scenario.override(package_return_inductance_h=2e-9,reason='Adverse package')
        config=load_design().configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                       sample_divider=64,pga_gain_db=39)
        environment=configured_environment(config,scenario)
        self.assertEqual(environment_converter_parameters(environment).temperature_k,298.15)
        self.assertEqual(environment['scenario_assumptions'],{'temperature_c':25})
        self.assertEqual(environment['operating_conditions']['temperature_c'],25)
        self.assertIn('not modeled',environment['operating_conditions']['scope'])
        with self.assertRaises(TypeError):scenario.assumptions['temperature_c']=30

    def test_unknown_or_out_of_window_conditions_fail_explicitly(self):
        from design_definition import Scenario
        from baseline_envelope import configured_environment
        config=load_design().configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                       sample_divider=64,pga_gain_db=39)
        for values in ({'supply_v':3.3},{'temperature_c':float('nan')},{'temperature_c':True}):
            with self.subTest(values=values),self.assertRaises(ValueError):Scenario(assumptions=values)
        with self.assertRaisesRegex(ValueError,'operating window'):
            configured_environment(config,Scenario(assumptions={'temperature_c':50}))


class NarrowbandConfigurationTests(unittest.TestCase):
    def test_direct_receiver_rejects_a_different_legal_initial_gain(self):
        from baseline_envelope import configured_environment,receiver_inventory_options
        from ble_packet import joined_scan_request
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                sample_divider=128,pga_gain_db=36)
        environment=configured_environment(config)
        self.assertEqual(receiver_inventory_options(environment)['initial_gain_db'],36)
        with self.assertRaisesRegex(ValueError,'initial gain conflicts'):
            joined_scan_request(environment,design.contract,initial_gain_db=39)

    def test_resolved_divider_and_initial_gain_reach_packet_receiver(self):
        from unittest.mock import patch
        from baseline_envelope import configured_environment,coupled_scan_request
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                sample_divider=128,pga_gain_db=36)
        environment=configured_environment(config)
        class ReachedReceiver(Exception):pass
        with patch('baseline_envelope.joined_scan_request',side_effect=ReachedReceiver) as receiver:
            with self.assertRaises(ReachedReceiver):
                coupled_scan_request(environment,design.contract,rx_options={},stimulus={'seed':81})
        self.assertEqual(receiver.call_args.kwargs['lo_divider'],128)
        self.assertEqual(receiver.call_args.kwargs['initial_gain_db'],36)
        self.assertEqual(receiver.call_args.kwargs['maximum_gain_db'],42)
        for options in ({'initial_gain_db':54},{'maximum_gain_db':60},{'noise_figure_db':0}):
            with self.subTest(options=options),self.assertRaisesRegex(ValueError,'conflict'):
                coupled_scan_request(environment,design.contract,rx_options=options,stimulus={'seed':81})


class WiredConfigurationTests(unittest.TestCase):
    def test_wired_campaign_rejections_keep_resolved_design_and_scenario(self):
        from unittest.mock import patch
        from baseline_envelope import wired_transmit_campaign,wired_recovery_campaign
        design=load_design()
        with patch('baseline_envelope.reference_payload_environment',return_value=(None,{'accepted':False})):
            reports=(wired_transmit_campaign(design.contract,include_swing_controls=False),
                     wired_recovery_campaign(design.contract))
        for report in reports:
            self.assertEqual(report['design_provenance'],design.provenance())
            self.assertEqual(len(report['cases']),3)
            for row in report['cases']:
                self.assertEqual(row['resolved_configuration']['line_rate_bps'],2.5e9)
                self.assertEqual(row['resolved_configuration']['host_word_hz'],312.5e6)
                self.assertTrue(all(change['reason'].startswith('Package uncertainty case:')
                                    for change in row['scenario_overrides']))

    def test_fixed_transport_fixture_rejects_other_resolved_rate_relationships(self):
        from baseline_envelope import configured_environment,wired_transmit_transport
        design=load_design()
        config=design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=16)
        with self.assertRaisesRegex(ValueError,'divide-by-eight'):
            wired_transmit_transport(configured_environment(config),frames=1)


class TransmitterConfigurationTests(unittest.TestCase):
    def test_selected_fpga_correction_parameters_reach_actual_preparation(self):
        from unittest.mock import patch
        from baseline_envelope import configured_environment
        from selected_rf import wideband_transmit
        design=load_design();architecture=design.architecture
        # FPGA preparation is outside the circuit-parameter override API.
        architecture['rf_interoperability']['fpga_tx_preparation'].update(
            taps=65,coefficient_fraction_bits=14)
        design=DesignDefinition.from_documents(design.contract,architecture)
        environment=configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.4e9,sample_divider=64))
        class ReachedCorrection(Exception):pass
        with patch('selected_rf.fpga_tx_filter_correction',side_effect=ReachedCorrection) as correction:
            with self.assertRaises(ReachedCorrection):wideband_transmit(environment,oversample=128)
        self.assertEqual(correction.call_args.kwargs['taps'],65)
        self.assertEqual(correction.call_args.kwargs['coefficient_fraction_bits'],14)
        self.assertEqual(correction.call_args.kwargs['cutoff_hz'],12e6)

    def test_whole_record_mask_screen_preserves_edges_and_rejects_strong_spur(self):
        import numpy as np
        from selected_rf import relative_burst_mask_screen
        mask=load_design().architecture['rf_interoperability']['tx_spectral_measurement']
        fs=80e6;t=np.arange(8192)/fs
        clean=np.ones(len(t),complex)
        quiet=relative_burst_mask_screen(clean,fs,mask)
        spur=relative_burst_mask_screen(clean+.5*np.exp(2j*np.pi*12e6*t),fs,mask)
        self.assertTrue(quiet['relative_energy_screen_pass'])
        self.assertFalse(spur['relative_energy_screen_pass'])
        self.assertGreater(spur['worst_relative_excess_db'],10.)
        scaled=relative_burst_mask_screen(3*clean,fs,mask)
        self.assertAlmostEqual(scaled['worst_relative_excess_db'],quiet['worst_relative_excess_db'],places=6)
        # Same impulse energy at the edge and center: no Hann taper may erase it.
        edge=np.zeros(len(t),complex);edge[0]=1
        center=np.roll(edge,len(t)//2)
        a=relative_burst_mask_screen(edge,fs,mask)
        z=relative_burst_mask_screen(center,fs,mask)
        self.assertAlmostEqual(a['worst_relative_excess_db'],z['worst_relative_excess_db'],places=10)
        self.assertFalse(quiet['qualification']);self.assertIsNone(quiet['mask_pass'])
        short=relative_burst_mask_screen(np.ones(16,complex),fs,mask)
        self.assertFalse(short['rbw_grid_resolved']);self.assertIsNone(short['relative_energy_screen_pass'])

    def test_fpga_correction_is_causal_and_does_not_renormalize(self):
        import numpy as np
        from selected_rf import fpga_tx_filter_correction
        kwargs=dict(sample_hz=37.5e6,filter_family='rx_all_pole_control',cutoff_hz=12e6)
        source=np.zeros(160,complex);source[64]=1+.5j
        corrected,metadata=fpga_tx_filter_correction(source,**kwargs)
        np.testing.assert_array_equal(corrected[:64],0.)
        np.testing.assert_allclose(corrected[64:113],np.asarray(metadata['coefficients'])*(1+.5j),atol=0,rtol=0)
        doubled,_=fpga_tx_filter_correction(2*source,**kwargs)
        np.testing.assert_allclose(doubled,2*corrected,atol=0,rtol=0)
        self.assertEqual(metadata['alignment_delay_s'],24/37.5e6)
        np.testing.assert_array_equal(corrected[113:],0.)

    def test_supply_gain_retains_step_history_across_packet_chunks(self):
        import numpy as np
        from selected_rf import tx_supply_gain
        from copy import deepcopy
        driver=deepcopy(load_design().architecture['blocks']['rfdriver']['parameters'])
        driver['supply_gain_model']=dict(dc_elasticity=1.,high_frequency_elasticity=.02,pole_hz=5e6)
        times=np.arange(401)*1e-9
        rails=np.where(times<100e-9,3.3,2.9)
        whole=tx_supply_gain(rails,3.3,driver,times)
        state={};parts=[]
        for lo,hi in ((0,100),(100,101),(101,177),(177,401)):
            parts.append(tx_supply_gain(rails[lo:hi],3.3,driver,times[lo:hi],state=state))
        np.testing.assert_allclose(np.concatenate(parts),whole,atol=1e-15,rtol=0)
        x=2.9/3.3-1
        expected=1+.02*x+.98*x*(1-np.exp(-2*np.pi*5e6*(times[100:]-times[100])))
        np.testing.assert_allclose(whole[100:],expected,atol=2e-15,rtol=0)
        reset=tx_supply_gain(rails[100:],3.3,driver,times[100:])
        self.assertGreater(whole[100]-reset[0],.1)
        saved=deepcopy(state)
        with self.assertRaisesRegex(ValueError,'advance'):
            tx_supply_gain(rails[-1:],3.3,driver,times[-1:],state=state)
        self.assertEqual(state,saved)
        with self.assertRaisesRegex(ValueError,'different configuration'):
            tx_supply_gain(rails[-1:],3.,driver,times[-1:]+1e-9,state=state)
        self.assertEqual(state,saved)

    def test_dynamic_gain_headroom_bound_charges_high_rail_prehistory(self):
        import numpy as np
        from copy import deepcopy
        from selected_rf import tx_amplitude_bound,tx_supply_gain
        design=load_design();driver=deepcopy(design.architecture['blocks']['rfdriver']['parameters'])
        req=design.contract['generic_configuration_target']['tx_amplitude_operating_requirement']
        driver['supply_gain_model']['high_frequency_elasticity']=1.
        memoryless=tx_amplitude_bound(req,driver_parameters=driver)
        driver['supply_gain_model']['high_frequency_elasticity']=.02
        dynamic=tx_amplitude_bound(req,driver_parameters=driver)
        self.assertLess(dynamic['correlated_supply_bound']['minimum_margin_v'],
                        memoryless['correlated_supply_bound']['minimum_margin_v'])
        low,high=req['supply_interval_v']
        gain=tx_supply_gain(np.array([high,low]),driver['gain_reference_v'],driver,np.array([0.,1e-9]))[-1]
        bound=dynamic['correlated_supply_bound']['endpoints'][0]['open_peak_bound_v']
        reconstructed_bound=dynamic['iq_operator_gain_bound']*req['reconstructed_complex_peak_v']+abs(dynamic['output_parameters']['lo_feedthrough'])
        self.assertAlmostEqual(bound,4.5*gain*reconstructed_bound,places=13)

    def test_driver_impedance_change_follows_independent_voltage_division(self):
        import numpy as np
        from selected_rf import transmit_output
        driver=load_design().architecture['blocks']['rfdriver']['parameters']
        signal=np.full(16,.001+0j);rails=np.full(16,3.3);phase=np.zeros(16)
        nominal,_,_=transmit_output(signal,rails,phase,driver_parameters=driver)
        changed=dict(driver,source_r_ohm_differential=80.)
        adverse,_,_=transmit_output(signal,rails,phase,driver_parameters=changed)
        np.testing.assert_allclose(adverse['envelope_v'],nominal['envelope_v']*90/130,rtol=1e-13)
        from selected_rf import tx_amplitude_bound
        variant=load_design().hypothetical(reason='Independent TX gain-law reference',changes={
            'blocks.rfdriver.parameters.gain_reference_v':3.0})
        variant_driver=variant.architecture['blocks']['rfdriver']['parameters']
        shifted,_,_=transmit_output(signal,rails,phase,driver_parameters=variant_driver)
        np.testing.assert_allclose(shifted['envelope_v'],nominal['envelope_v']*1.1,rtol=1e-13)
        requirement=variant.contract['generic_configuration_target']['tx_amplitude_operating_requirement']
        first=tx_amplitude_bound(requirement,driver_parameters=driver)
        second=tx_amplitude_bound(requirement,driver_parameters=variant_driver)
        self.assertAlmostEqual(second['open_peak_bound_v']/first['open_peak_bound_v'],1.1)
        for consume in (lambda d:transmit_output(signal,rails,phase,driver_parameters=d),
                        lambda d:tx_amplitude_bound(requirement,driver_parameters=d)):
            missing=dict(driver);del missing['gain_reference_v']
            with self.assertRaises(KeyError):consume(missing)
        with self.assertRaisesRegex(ValueError,'conflicts'):
            transmit_output(signal,rails,phase,driver_parameters=variant_driver,gain_reference_v=3.3)

    def test_transmitter_validates_before_waveform_generation(self):
        from unittest.mock import patch
        from baseline_envelope import configured_environment
        from selected_rf import wideband_transmit
        design=load_design()
        environment=configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.4e9,sample_divider=64))
        for options in ({'oversample':True},{'oversample':3},{'noise':1},
                        {'input_rms_codes':True},{'input_rms_codes':float('nan')},
                        {'nominal_gain':True},{'nominal_gain':float('inf')}):
            with self.subTest(options=options),patch('selected_rf.he_source') as source:
                with self.assertRaises(ValueError):wideband_transmit(environment,**options)
                source.assert_not_called()
        receive=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        with patch('selected_rf.he_source') as source:
            with self.assertRaisesRegex(ValueError,'Transmitter configuration'):
                wideband_transmit(receive)
            source.assert_not_called()
        import copy
        from ble_packet import transmitted_scan_response
        for field in ('tx_gain','tx_gain_code','resolved_tx_gain'):
            broken=copy.deepcopy(environment);del broken['resolved_configuration'][field]
            with self.subTest(field=field),patch('selected_rf.he_source') as source:
                with self.assertRaisesRegex(ValueError,'Resolved TX gain'):
                    wideband_transmit(broken)
                with self.assertRaisesRegex(ValueError,'Resolved TX gain'):
                    transmitted_scan_response({},broken,design.contract)
                source.assert_not_called()
        for field in ('tx_gain_code','resolved_tx_gain'):
            broken=copy.deepcopy(environment);broken['resolved_configuration'][field]+=1
            with self.assertRaisesRegex(ValueError,'TX gain code conflicts'):
                wideband_transmit(broken)
            with self.assertRaisesRegex(ValueError,'TX gain code conflicts'):
                transmitted_scan_response({},broken,design.contract)
        with self.assertRaisesRegex(ValueError,'TX gain conflicts'):
            transmitted_scan_response({},environment,design.contract,nominal_gain=1.)
        for enabled in (True,False):
            result=wideband_transmit(environment,oversample=128,noise=enabled)
            self.assertIs(result['noise_enabled'],enabled)
            self.assertEqual(result['noise_sources'],dict(converter=enabled,aperture=enabled))
            self.assertEqual(result['oversample'],128)

    def test_wake_rejection_records_transmit_configuration(self):
        from unittest.mock import patch
        from baseline_envelope import transmitter_wake_campaign
        design=load_design()
        with patch('baseline_envelope.reference_payload_environment',return_value=(None,{'accepted':False})):
            report=transmitter_wake_campaign(design.contract)
        self.assertEqual(report['design_provenance'],design.provenance())
        for row in report['cases']:
            self.assertEqual(row['resolved_configuration']['direction'],'tx')
            self.assertEqual(row['resolved_configuration']['sample_divider'],64)
            self.assertTrue(row['scenario_overrides'])


class ExplicitExperimentTests(unittest.TestCase):
    def test_converter_variants_have_distinct_snapshots_and_reasons(self):
        from baseline_envelope import converter_design_cases,configured_environment,environment_converter_parameters
        design=load_design();fingerprint=design.fingerprint
        cases=dict(converter_design_cases(design))
        self.assertEqual(len(cases),4)
        self.assertEqual(len({case.fingerprint for case in cases.values()}),4)
        variant=cases['combined_slow_probe']
        config=variant.configure(engine='rf',direction='rx',reference_hz=2.484e9,sample_divider=64,pga_gain_db=42)
        p=environment_converter_parameters(configured_environment(config))
        self.assertEqual((p.dac_tau_s,p.reference_r_ohm,p.reference_cap_f),(.4e-9,100.,50e-12))
        self.assertTrue(variant.provenance()['circuit_experiments'][0]['reason'])
        self.assertEqual(design.fingerprint,fingerprint)

    def test_unsupported_gain_requires_a_hypothetical_design(self):
        from baseline_envelope import configured_environment
        from selected_rf import wideband_receive
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=42.)
        environment=configured_environment(config)
        with self.assertRaisesRegex(ValueError,'Unsupported gain'):
            wideband_receive(environment,gain_settings_db=(54.,),
                gain_hypothesis_reason='A reason alone cannot change the configured circuit')
        changes={f'blocks.{lane}.parameters.gain_db':design.architecture['blocks'][lane]['parameters']['gain_db']+[54.]
                 for lane in ('pga_i','pga_q')}
        variant=design.hypothetical(reason='Estimate missing gain requirement',changes=changes)
        alternative=configured_environment(variant.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=54.))
        result=wideband_receive(alternative,oversample=128,noise=False)
        self.assertEqual(result['design_provenance'],variant.provenance())
        self.assertEqual(result['resolved_configuration']['pga_gain_db'],54.)
        del environment['resolved_configuration']
        with self.assertRaisesRegex(ValueError,'requires a resolved configuration'):
            wideband_receive(environment)

    def test_selected_package_case_uses_the_supplied_snapshot(self):
        from baseline_envelope import network_cases,BASELINE_PACKAGE_CASE
        design=load_design().hypothetical(reason='Package target experiment',changes={
            'blocks.power.parameters.shared_return_l_h':.35e-9,
            'blocks.power.parameters.reduced_pdn_model.network.die_esl':.3e-9})
        cases={name:(return_l,esl) for name,return_l,esl in network_cases(design)}
        self.assertEqual(cases[BASELINE_PACKAGE_CASE],(.35e-9,.3e-9))
        self.assertEqual(cases['higher_inductance_probe'],(2e-9,1e-9))


class SnapshotEntryTests(unittest.TestCase):
    def test_changed_contract_requires_an_explicit_snapshot(self):
        from baseline_envelope import design_for_contract,selected_environment
        current=load_design()
        contract=current.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        with self.assertRaisesRegex(ValueError,'explicit design snapshot'):
            design_for_contract(contract)
        explicit=DesignDefinition.from_documents(contract,current.architecture)
        self.assertIs(design_for_contract(contract,explicit),explicit)
        environment=selected_environment(contract,'wire',2.5e9,312.5e6,design=explicit)
        self.assertEqual(environment['transport_parameters']['startup_s'],30e-6)
        self.assertEqual(environment['design_provenance'],explicit.provenance())

    def test_convenience_environment_preserves_supplied_hypothetical_snapshot(self):
        from baseline_envelope import selected_environment,design_for_contract
        design=load_design().hypothetical(reason='Package sensitivity',changes={
            'blocks.power.parameters.shared_return_l_h':.35e-9})
        environment=selected_environment(design.contract,'rf',2.4e9,150e6,design=design)
        self.assertEqual(environment['network']['return_l_h'],.35e-9)
        self.assertEqual(environment['design_provenance'],design.provenance())
        contract=design.contract;contract['unexpected_test_key']=True
        with self.assertRaisesRegex(ValueError,'Contract does not match'):
            design_for_contract(contract,design)

    def test_lifecycle_rejects_an_unimplemented_hypothetical_dac_format(self):
        from selected_lifecycle import ownership_load_trace
        design=load_design().hypothetical(reason='Different DAC word-format experiment',changes={
            'blocks.dac_i.parameters.transport_bits':11})
        with self.assertRaisesRegex(ValueError,'Lifecycle DAC adapter'):
            ownership_load_trace(design.contract,design=design)


class WiredProbeSnapshotTests(unittest.TestCase):
    def test_baseline_runner_rejects_source_changes_and_records_stable_snapshot(self):
        from unittest.mock import patch
        import baseline_envelope as baseline
        for changed in (False,True):
            with patch.object(baseline,'baseline_source_hashes',side_effect=[{'fixture':'before'},{'fixture':'after' if changed else 'before'}]), \
                 patch.object(baseline,'narrowband_exchange',return_value={}), \
                 patch.object(baseline,'converter_feedback',return_value={}), \
                 patch.object(baseline,'wideband_diagnosis',return_value={}), \
                 patch.object(baseline,'assemble_baseline',return_value={'independent_fixture':True}):
                if changed:
                    with self.assertRaisesRegex(RuntimeError,'Sources changed during baseline'):
                        baseline.run()
                else:
                    result=baseline.run()
                    self.assertEqual(result['sources_sha256'],{'fixture':'before'})
                    self.assertIn('unchanged across',result['source_verification'])

    def test_baseline_rejects_foreign_or_unbound_campaigns_before_simulation(self):
        from concurrent.futures import Future
        from unittest.mock import patch
        import baseline_envelope as baseline
        design=load_design()
        other=design.hypothetical(reason='Foreign baseline capture',changes={
            'blocks.ctle.parameters.dc_gain':2.})
        for index in range(3):
            for bad in ({},dict(design_provenance=other.provenance())):
                futures=[]
                for position in range(3):
                    future=Future()
                    future.set_result(bad if position==index else dict(design_provenance=design.provenance()))
                    futures.append(future)
                with patch.object(baseline,'clock_screen_environment') as simulation:
                    with self.assertRaisesRegex(ValueError,'baseline input does not match'):
                        baseline.assemble_baseline(design.contract,*futures,design=design)
                    simulation.assert_not_called()

    def test_baseline_accepts_campaign_roots_from_supplied_variant(self):
        from concurrent.futures import Future
        from unittest.mock import patch
        import baseline_envelope as baseline
        design=load_design().hypothetical(reason='Explicit baseline variant',changes={
            'blocks.ctle.parameters.dc_gain':2.})
        futures=[]
        for _ in range(3):
            future=Future();future.set_result(dict(design_provenance=design.provenance()))
            futures.append(future)
        # Stop at the first simulation boundary: this checks admission only.
        with patch.object(baseline,'clock_screen_environment',side_effect=RuntimeError('admitted fixture')) as simulation:
            with self.assertRaisesRegex(RuntimeError,'admitted fixture'):
                baseline.assemble_baseline(design.contract,*futures,design=design)
            self.assertEqual(simulation.call_count,1)
            self.assertIs(simulation.call_args.args[0],design)

    def test_baseline_receiver_inputs_follow_shared_hardware(self):
        from baseline_envelope import configured_environment,baseline_wired_receiver_inputs
        design=load_design().hypothetical(reason='Baseline receiver hardware propagation',changes={
            'blocks.ctle.parameters.zero_s':240e-12,
            'blocks.ctle.parameters.dc_gain':2.,
            'blocks.cdr.parameters.detector_jitter_rms_s':7e-12,
            'blocks.cdr.parameters.holdover_bits':32})
        environment=configured_environment(design.configure(engine='wire',direction='duplex',
            reference_hz=2.5e9,host_divider=8))
        inputs=baseline_wired_receiver_inputs(environment,label='hardware variant')
        scenario=inputs['timing_scenario']
        self.assertEqual(scenario['ctle_zero_s'],240e-12)
        self.assertEqual(scenario['detector_noise_rms_s'],7e-12)
        self.assertEqual(scenario['holdover_ui'],32)
        self.assertAlmostEqual(scenario['signal_scale'],2*environment['ledger']['local_payload_clock_core_rail_v']/3.3)
        cap=environment['wired_pad_capacitance_f']
        self.assertAlmostEqual(inputs['channel_case'][0],(cap[0][0]+cap[1][1]-cap[0][1]-cap[1][0])/2,places=24)
        missing=dict(environment);del missing['wired_ctle_parameters']
        with self.assertRaises(KeyError):baseline_wired_receiver_inputs(missing,label='incomplete')

    def test_shared_equalizer_gain_changes_actual_receiver_voltage(self):
        from baseline_envelope import configured_environment,wired_receiver_inventory
        from wired_envelope import physical_receiver
        design=load_design()
        variant=design.hypothetical(reason='Equalizer DC gain uncertainty',changes={
            'blocks.ctle.parameters.dc_gain':2.})
        observed=[]
        for snapshot in (design,variant):
            environment=configured_environment(snapshot.configure(engine='wire',direction='duplex',
                reference_hz=2.5e9,host_divider=8))
            parameters=wired_receiver_inventory(environment)
            # Noise-free constant input is an independent DC transfer-law fixture.
            impairment=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
                signal_scale=parameters['ctle_dc_gain'],ctle_zero_s=parameters['ctle_zero_s'],
                ctle_pole_s=parameters['ctle_pole_s'],detector_noise_rms_s=parameters['detector_noise_rms_s'],
                holdover_ui=parameters['holdover_ui'])
            receiver=physical_receiver([1]*32,2.5e9,0.,0.,100e-12,parameters['pad_cap_f'],impairment)
            observed.append(receiver.voltage(20.))
        self.assertAlmostEqual(observed[0],.4,places=10)
        self.assertAlmostEqual(observed[1],.8,places=10)

    def test_loaded_recovery_uses_shared_equalizer_at_receiver_boundary(self):
        from unittest.mock import patch
        from selected_lifecycle import loaded_wired_recovery
        from baseline_envelope import configured_environment,wired_receiver_inventory
        design=load_design().hypothetical(reason='Loaded receiver equalizer uncertainty',changes={
            'model_assumptions.wired_supply_gain.parameters.reference_voltage_v':3.0,
            'blocks.ctle.parameters.zero_s':240e-12,'blocks.ctle.parameters.dc_gain':2.,
            'blocks.cdr.parameters.detector_jitter_rms_s':7e-12,
            'blocks.cdr.parameters.holdover_bits':48})
        environment=configured_environment(design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8))
        expected=wired_receiver_inventory(environment)
        class ReachedReceiver(Exception):pass
        with patch('wired_envelope.physical_receiver',side_effect=ReachedReceiver) as receiver:
            with self.assertRaises(ReachedReceiver):loaded_wired_recovery(design.contract,design=design)
        self.assertEqual(receiver.call_args.kwargs['cap'],expected['pad_cap_f'])
        self.assertEqual(receiver.call_args.kwargs['impairment']['ctle_zero_s'],240e-12)
        self.assertEqual(receiver.call_args.kwargs['impairment']['detector_noise_rms_s'],7e-12)
        self.assertEqual(receiver.call_args.kwargs['impairment']['holdover_ui'],48)
        self.assertAlmostEqual(receiver.call_args.kwargs['impairment']['signal_scale'],
            2*environment['ledger']['local_payload_clock_core_rail_v']/3.0)
        malformed=dict(environment,wired_pad_capacitance_f=[[3e-12,-.1e-12],[-.1e-12,4e-12]])
        with self.assertRaisesRegex(ValueError,'coupled-pad'):wired_receiver_inventory(malformed)
        for matrix in ([[1e-12,-2e-12],[-2e-12,1e-12]],
                       [[3e-12,-.1e-12],[-.2e-12,3e-12]],
                       [[float('nan'),0],[0,3e-12]]):
            with self.subTest(matrix=matrix),self.assertRaises(ValueError):
                wired_receiver_inventory(dict(environment,wired_pad_capacitance_f=matrix))
        missing=dict(environment);del missing['wired_ctle_parameters']
        with self.assertRaises(KeyError):wired_receiver_inventory(missing)

    def test_recovery_campaign_passes_inventory_pad_and_ctle_to_receiver(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from baseline_envelope import wired_recovery_campaign
        design=load_design().hypothetical(reason='Equalizer transfer uncertainty',changes={
            'blocks.ctle.parameters.zero_s':240e-12,
            'blocks.ctle.parameters.pole_s':90e-12,
            'blocks.ctle.parameters.dc_gain':2.,
            'blocks.cdr.parameters.detector_jitter_rms_s':7e-12,
            'blocks.cdr.parameters.holdover_bits':48})
        calls=[]
        def receiver(bits,rate,phase,ppm,tau,cap,impairment,**kwargs):
            calls.append((cap,dict(impairment)))
            return SimpleNamespace(rail_observations=[3.3],first_qualified_bit=1,
                qualification_losses=0,bit_index=1)
        def lifecycle(**kwargs):
            kwargs['source_factory']([0,1],2.5e9,0.,0.)
            return {'cases':[{'minimum_release_met':True}]}
        with patch('baseline_envelope.network_cases',return_value=[('fixture',1e-9,1e-10)]),\
             patch('baseline_envelope.reference_payload_environment',side_effect=lambda e,*a,**k:(e,{})),\
             patch('baseline_envelope.physical_receiver',side_effect=receiver),\
             patch('behavioral.raw_host_alignment_controls',side_effect=lifecycle):
            result=wired_recovery_campaign(design.contract,design=design)
        network=design.architecture['pad_behavioral_contract']['shared_wired_network']
        expected_cap=network['base_shunt_cap_f_per_leg']+network['inactive_branch_cap_f_per_leg']+2*network['mutual_cap_f']
        self.assertEqual(len(calls),6)
        for cap,impairment in calls:self.assertAlmostEqual(cap/1e-12,expected_cap/1e-12)
        for _,impairment in calls:
            self.assertEqual(impairment['detector_noise_rms_s'],7e-12)
            self.assertEqual(impairment['holdover_ui'],48)
        self.assertNotIn('ctle_zero_s',calls[0][1])
        self.assertAlmostEqual(calls[2][1]['ctle_zero_s']/1e-12,180.)
        self.assertAlmostEqual(calls[4][1]['ctle_zero_s']/1e-12,240.)
        self.assertAlmostEqual(calls[4][1]['ctle_pole_s']/1e-12,90.)
        self.assertAlmostEqual(calls[4][1]['signal_scale'],2*calls[0][1]['signal_scale'])
        self.assertEqual(result['cases'][0]['receiver_fixture']['role'],'diagnostic_equalizer_control')
        self.assertEqual(result['cases'][-1]['receiver_fixture']['role'],'nominal_equalizer')
        self.assertEqual(result['design_provenance'],design.provenance())

    def test_probe_preserves_snapshot_and_labels_capacitance_experiment(self):
        from unittest.mock import patch
        import wired_lock_probe as probe
        baseline=load_design()
        design=baseline.hypothetical(reason='Independent alternate decoupling fixture',changes={
            'blocks.power.parameters.reduced_pdn_model.network.die_c':700e-12})
        def pass_clock(environment,*args,**kwargs):return environment,{'accepted':True}
        with patch.object(probe.b,'reference_payload_environment',side_effect=pass_clock):
            nominal,row=probe.probe_environment(design.contract,.75,design=design)
            changed,variant=probe.probe_environment(design.contract,.75,design=design,die_cap_f=1e-9)
        self.assertEqual(nominal['network']['network']['die_c'],700e-12)
        self.assertEqual(row['design_provenance'],design.provenance())
        self.assertEqual(changed['network']['network']['die_c'],1e-9)
        self.assertNotEqual(variant['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(len(variant['design_provenance']['circuit_experiments']),2)
        self.assertEqual(variant['resolved_configuration']['line_rate_bps'],2.5e9)
        self.assertEqual(variant['scenario_stimuli']['reference_peak_v'],.75)
        self.assertEqual(design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['die_c'],700e-12)

    def test_rejected_rf_clock_retains_configuration_and_probe_assumptions(self):
        from unittest.mock import patch
        import wired_lock_probe as probe
        design=load_design()
        loads=[dict(owner='timing',mean_a=.01,event_hz=150e6,tau_s=.2e-9,harmonics=4)]
        with patch.object(probe.b,'reference_payload_environment',return_value=(None,{'accepted':False})):
            environment,row=probe.probe_environment(design.contract,.5,engine='rf',carrier=2.4e9,
                internal_loads=loads,sensitivity_ps_per_mv=.025,design=design)
        self.assertIsNone(environment)
        self.assertEqual(row['design_provenance'],design.provenance())
        self.assertEqual(row['resolved_configuration']['sample_divider'],64)
        self.assertEqual(row['probe_assumptions']['internal_switching_loads'],loads)
        self.assertEqual(row['probe_assumptions']['sensitivity_ps_per_mv'],.025)

    def test_adverse_pulse_budget_failure_is_reported_without_masking_other_errors(self):
        from unittest.mock import patch
        import feed_failure_probe as probe
        with patch.object(probe.b,'reference_payload_environment',
                side_effect=ValueError('Internal pulse mean exceeds owner DC budget')):
            environment,row=probe.loaded_probe({})
        self.assertIsNone(environment)
        self.assertEqual(row['status'],'load_rejected')
        with patch.object(probe.b,'reference_payload_environment',side_effect=ValueError('unrelated defect')):
            with self.assertRaisesRegex(ValueError,'unrelated defect'):probe.loaded_probe({})


class RFFeedManifestTests(unittest.TestCase):
    def test_all_output_modes_check_freshness_even_when_clock_is_rejected(self):
        from unittest.mock import patch
        import feed_rf_probe as probe
        design=load_design()
        context=dict(design_provenance=design.provenance(),status='load_rejected')
        hashes=probe.source_hashes()
        for name in ('verification/converter_dynamics.py','verification/selected_rf.py',
                     'verification/feed_failure_probe.py','system_model/connected/protocol_pad.py'):
            self.assertIn(name,hashes)
        for run in (probe.main,probe.paths,lambda:probe.paths(True),probe.spectra):
            with self.subTest(mode=run),patch.object(probe,'feed_environment',return_value=(None,context)),                     patch.object(probe.b,'write_evidence') as save:
                run()
                self.assertEqual(save.call_args.args[1]['sources_sha256'],hashes)
                self.assertEqual(save.call_args.args[1]['design_provenance'],design.provenance())
            with self.subTest(stale_mode=run),patch.object(probe,'feed_environment',return_value=(None,context)),                     patch.object(probe,'source_hashes',side_effect=[hashes,{}]),                     patch.object(probe.b,'write_evidence') as save:
                with self.assertRaisesRegex(RuntimeError,'Sources changed during RF feed'):
                    run()
                save.assert_not_called()


class PreemphasisSnapshotTests(unittest.TestCase):
    def test_unsupported_converter_snapshot_fails_before_waveform_work(self):
        from unittest.mock import patch
        import rf_filter_tradeoff as screen
        design=load_design().hypothetical(reason='Unsupported converter adapter fixture',changes={
            'blocks.dac_i.parameters.differential_peak_v':.8})
        with patch.object(screen,'tx_preemphasis_coefficients') as coefficients:
            with self.assertRaisesRegex(ValueError,'1 V normalized full scale'):
                screen.tx_preemphasis_screen(design=design)
        coefficients.assert_not_called()

    def test_missing_spectral_measurement_cannot_inherit_a_default(self):
        design=load_design();architecture=design.architecture
        del architecture['rf_interoperability']['tx_spectral_measurement']['rbw_hz']
        with self.assertRaisesRegex(ValueError,'Missing required design parameter'):
            DesignDefinition.from_documents(design.contract,architecture)


class USBInventorySnapshotTests(unittest.TestCase):
    def test_supply_preserves_design_and_records_uncertainty(self):
        from selected_revision_check import usb_inventory_supply
        design=load_design().hypothetical(reason='Alternate USB package fixture',changes={
            'blocks.power.parameters.shared_return_l_h':.4e-9})
        result=usb_inventory_supply(design.contract,design.architecture,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['host_clock_source'],'host_follow')
        self.assertEqual(result['scenario_overrides'],[])
        stressed=usb_inventory_supply(design.contract,design.architecture,design=design,
                                      return_l=2e-9,die_esl=1e-9)
        self.assertEqual(stressed['design_provenance'],design.provenance())
        self.assertEqual(len(stressed['scenario_overrides']),2)
        self.assertTrue(all(item['reason'] for item in stressed['scenario_overrides']))
        self.assertLess(abs(stressed['ledger']['power_balance_residual_w']),1e-12)

    def test_supply_uses_shared_host_rate_and_rejects_mixed_documents(self):
        from selected_revision_check import usb_inventory_supply
        baseline=load_design();architecture=baseline.architecture
        architecture['direct_stream_service']['budget']['host_hz']=80e6
        design=DesignDefinition.from_documents(baseline.contract,architecture)
        result=usb_inventory_supply(design.contract,design.architecture,design=design)
        self.assertEqual(result['host_word_hz'],80e6)
        with self.assertRaisesRegex(ValueError,'conflict'):
            usb_inventory_supply(baseline.contract,baseline.architecture,design=design)


class PacketScreenSnapshotTests(unittest.TestCase):
    def test_rejected_clock_keeps_packet_configuration_and_stimulus(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design().hypothetical(reason='Packet package fixture',changes={
            'blocks.power.parameters.shared_return_l_h':.4e-9})
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})):
            ble=screen.common_rf_packet_screen(design.contract,design.architecture,design=design)
            wide=screen.common_wideband_packet_screen(design.contract,design.architecture,
                                                     wanted_dbm=-75.,design=design)
        for result in (ble,wide):
            self.assertEqual(result['status'],'clock_rejected')
            self.assertEqual(result['design_provenance'],design.provenance())
            self.assertEqual(result['resolved_configuration']['sample_divider'],64)
        self.assertEqual(ble['resolved_configuration']['pga_gain_db'],39.)
        self.assertEqual(wide['scenario_stimuli']['wanted_dbm'],-75.)
        self.assertEqual(wide['scenario_stimuli']['blocker_dbm'],-30.)

    def test_wideband_receives_shared_comparator_and_rejects_mixed_documents(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import wideband_packet
        base=load_design()
        design=base.hypothetical(reason='Comparator timing fixture',changes={
            'model_assumptions.paired_sar_comparator.parameters.tau_s':70e-12})
        def clock(environment,*args,**kwargs):return environment,{}
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(wideband_packet,'run_acquisition_case',return_value={
                 'payload_correct':True,'analog':{'numerical_feedback_converged':True}}) as receiver:
            result=screen.common_wideband_packet_screen(design.contract,design.architecture,design=design)
        self.assertEqual(receiver.call_args.kwargs['comparator_model']['tau_s'],70e-12)
        self.assertEqual(result['design_provenance'],design.provenance())
        with self.assertRaisesRegex(ValueError,'conflict'):
            screen.packet_environment(base.contract,base.architecture,design=design,
                                      gain_db=39.,wanted_dbm=-80.)

    def test_reference_clock_flag_is_json_serializable(self):
        import numpy as np
        from baseline_envelope import reference_edge_screen
        result=reference_edge_screen(100e6,np.complex128(.5),[(10e6,np.complex128(.01))])
        self.assertIs(type(result['incremental_envelope_met']),bool)
        json.dumps(result)


class TransmitScreenSnapshotTests(unittest.TestCase):
    def test_rejected_clock_preserves_tx_configuration_and_controls(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})) as clock:
            result=screen.common_tx_screen(design.contract,design.architecture,design=design,
                input_rms_codes=120.,driver_gain=5.,signal_loop_nh=2.,series_match_pf=1.)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['direction'],'tx')
        self.assertEqual(clock.call_args.args[0]['resolved_configuration']['inventory_mode'],'rf_tx')
        self.assertEqual(result['stimulus']['input_rms_codes'],120.)
        self.assertEqual(result['selected_controls']['driver_gain_requested'],5.)
        self.assertEqual(result['rf_load_hypothesis']['bond_loop_h'],2e-9)
        self.assertEqual(result['status'],'clock_rejected')

    def test_illegal_drive_setting_rejected_before_clock_work(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        with patch.object(screen.b,'reference_payload_environment') as clock:
            with self.assertRaisesRegex(ValueError,'TX gain outside'):
                screen.common_tx_screen(design.contract,design.architecture,driver_gain=20.)
        clock.assert_not_called()


class ConverterScreenSnapshotTests(unittest.TestCase):
    def test_variants_bind_sar_and_comparator_to_their_own_snapshots(self):
        from selected_revision_check import converter_timing_variants
        from converter_dynamics import parameters_from_inventory
        design=load_design();variants=list(converter_timing_variants(design))
        self.assertEqual(len(variants),6)
        self.assertEqual(variants[0][1].provenance(),design.provenance())
        self.assertEqual(len({v.fingerprint for _,v in variants}),6)
        for name,variant in variants:
            p=parameters_from_inventory(variant.architecture)
            if name=='combined_loading_stress':
                self.assertEqual(p.reference_r_ohm,100.)
                self.assertEqual(p.reference_limit_a,.5e-3)
                self.assertEqual(p.diagnostic_input_cap_f,150e-15)
                self.assertTrue(variant.provenance()['circuit_experiments'])
        self.assertNotEqual(parameters_from_inventory(design.architecture).reference_r_ohm,100.)

    def test_clock_rejections_keep_each_variant_without_running_converter(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import converter_dynamics
        design=load_design()
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})), \
             patch.object(converter_dynamics,'tone_precision') as converter:
            report=screen.converter_timing_screen(design.contract,design.architecture,design=design)
        converter.assert_not_called()
        self.assertEqual(len(report['cases']),6)
        for row in report['cases']:
            self.assertFalse(row['conditional_pass'])
            self.assertEqual(row['resolved_configuration']['design_fingerprint'],
                             row['design_provenance']['design_fingerprint'])
            self.assertEqual(row['resolved_configuration']['direction'],'rx')

    def test_admitted_tones_use_variant_environment_and_parameter_pairs(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import converter_dynamics
        design=load_design();seen=[]
        def clock(environment,*args,**kwargs):return environment,{}
        def tone(environment,parameters,**options):
            self.assertEqual(environment['converter_parameters']['reference_r_ohm'],parameters.reference_r_ohm)
            seen.append((environment['design_provenance']['design_fingerprint'],options['comparator_model']['tau_s']))
            return dict(fullscale_normalized_enob=[10.,10.],numerical_feedback_converged=True,
                converter=dict(actual_completion_margin_s=1e-9,schedule_margin_s=2e-9))
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(converter_dynamics,'tone_precision',side_effect=tone):
            report=screen.converter_timing_screen(design.contract,design.architecture,design=design)
        self.assertEqual(len(seen),6)
        self.assertEqual(len({fingerprint for fingerprint,_ in seen}),6)
        self.assertTrue(all(row['conditional_pass'] for row in report['cases']))

        stricter_q=design.hypothetical(reason='Independent per-lane precision allocation',changes={
            'blocks.adc_q.parameters.enob_target':9.})
        # Independent observations: I exceeds 8 bits, Q misses its 9-bit target.
        observed=dict(fullscale_normalized_enob=[10.,8.5],numerical_feedback_converged=True,
            converter=dict(actual_completion_margin_s=1e-9,schedule_margin_s=2e-9))
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(converter_dynamics,'tone_precision',return_value=observed):
            report=screen.converter_timing_screen(stricter_q.contract,stricter_q.architecture,design=stricter_q)
        for row in report['cases']:
            self.assertEqual(row['acceptance']['precision_margin_bits'],-.5)
            self.assertFalse(row['conditional_pass'])


class CDRScreenSnapshotTests(unittest.TestCase):
    def test_phase_bank_candidate_resolves_through_shared_hardware(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        base=load_design();fingerprint=base.fingerprint
        candidate=screen.cdr_phase_bank_candidate(base).hypothetical(reason='Shared candidate binding probe',changes={
            'blocks.cdr.parameters.periodic_clock_compute_delay_s':48e-6,
            'blocks.cdr.parameters.period_control_lsb_ppm':2.,
            'blocks.cdr.parameters.detector_jitter_rms_s':.7e-12,
            'blocks.cdr.parameters.holdover_bits':256})
        with patch.object(screen.b,'reference_payload_environment',side_effect=lambda env,*a,**k:(env,{})), \
             patch.object(screen.b,'causal_receiver_envelope',return_value={'cases':[]}) as receiver:
            report=screen.configured_phase_bank_tracking_screen(candidate,source_bit_count=2600,inserted_gaps=())
        controls=receiver.call_args.kwargs['timing_scenarios'][0]
        self.assertEqual(controls['periodic_clock_compute_delay_s'],48e-6)
        self.assertEqual(controls['period_control_lsb_ppm'],2.)
        self.assertEqual(controls['phase_control_steps'],4096)
        self.assertEqual(controls['detector_noise_rms_s'],.7e-12)
        self.assertEqual(controls['holdover_ui'],256)
        self.assertTrue(report['resolved_configuration']['cdr_periodic_tracking'])
        link=controls['periodic_observation_link']
        self.assertEqual(link['word_bits'],10)
        self.assertEqual(link['word_hz'],report['resolved_configuration']['host_word_hz'])
        self.assertGreater(link['latency_s'],128/link['word_hz'])

        self.assertTrue(report['receiver_parameters_from_design'])
        self.assertEqual(report['design_provenance'],candidate.provenance())
        self.assertEqual(base.fingerprint,fingerprint)
        self.assertEqual(base.architecture['blocks']['slicer']['parameters']['tracking_sampler_count'],98)
        self.assertEqual(candidate.architecture['nets']['phase_code']['electrical']['conductors'],9)
        from wired_envelope import physical_receiver
        cap,tau=receiver.call_args.kwargs['channel_cases'][0]
        rx=physical_receiver([0,1]*1500,2.5e9,.1,100.,tau,cap,controls)
        self.assertEqual(rx.periodic_clock_controller.compute_delay_ui,48e-6*2.5e9)
        self.assertEqual(rx.detector_phase_bins,96)
        self.assertEqual(rx.period_control_lsb,2e-6)
        # Actual free-running sample time, not merely reported telemetry, must
        # integrate the quantized period. Disable feedback in this isolated probe.
        rx.frequency=0.;rx.correction=3.2e-6
        rx.phase_gain=0.;rx.frequency_gain=0.;rx.frequency_slope=0.
        rx.frequency_slope_gain=0.
        before_phase=rx.phase
        rx.phase_control_residue=.6/4096
        self.assertAlmostEqual(rx.commanded_period_offset(),4e-6)
        rx.forecast(0)
        predicted=rx.predicted[0]
        self.assertAlmostEqual(predicted.phase-before_phase,40e-6-1/4096,places=10)
        self.assertAlmostEqual(predicted.phase_control_residue,-.4/4096)
        self.assertEqual(rx.phase_control_residue,.6/4096)
        self.assertEqual(rx.phase,before_phase)

        with self.assertRaisesRegex(ValueError,'design snapshot'):
            screen.configured_phase_bank_tracking_screen(candidate,phase_gain=.1)

    def test_phase_bank_hardware_must_cover_its_observations(self):
        from selected_revision_check import cdr_phase_bank_candidate
        candidate=cdr_phase_bank_candidate(load_design())
        for path,value in ((('blocks','slicer','parameters','tracking_sampler_count'),97),
                (('blocks','cdr','parameters','phase_steps'),32),
                (('blocks','cdr','parameters','period_control_lsb_ppm'),-1.),
                (('blocks','cdr','parameters','phase_control_steps'),1.5),
                (('nets','phase_code','electrical','conductors'),8),
                (('blocks','cdr','parameters','acquisition_timeout_ui'),1<<24)):
            architecture=candidate.architecture;target=architecture
            for key in path[:-1]:target=target[key]
            target[path[-1]]=value
            with self.assertRaises(ValueError):DesignDefinition.from_documents(candidate.contract,architecture)

    def test_holdover_pass_cannot_hide_tracking_frequency_failure(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        d=load_design()
        threshold=d.architecture['cdr_traffic_requirements']['selected_budget']['qualified_residual_frequency_error_target_ppm']
        for worst,accepted in ((threshold-.001,True),(threshold+.001,False)):
            # Acceptance-only fixture: every older diagnostic gate passes.
            case=dict(heldout_errors=0,heldout_policy_valid_fraction=1.,qualification_losses=0,
                heldout_instantaneous_residual_bound_violations=0,heldout_qualified_fraction=1.,
                measured_gap_phase={'scored_samples_outside_quarter_ui':0},
                heldout_free_run_residual_abs_ppm_quantiles=[10.,40.,worst])
            with patch.object(screen.b,'reference_payload_environment',side_effect=lambda env,*a,**k:(env,{})), \
                 patch.object(screen.b,'causal_receiver_envelope',return_value={'cases':[case]}):
                report=screen.cdr_full_cycle_screen(d.contract,d.architecture,design=d,window_screen=True)
            row=report['cases'][0]
            self.assertEqual(row['tracking_frequency_target_ppm'],threshold)
            self.assertEqual(row['checks']['tracking_frequency_target'],accepted)
            self.assertTrue(all(v for k,v in row['checks'].items() if k!='tracking_frequency_target'))
            self.assertEqual(row['conditional_acceptance'],accepted)
            with patch.object(screen,'configured_phase_bank_tracking_screen',return_value={
                    'result':{'cases':[dict(case)]},'model_assumptions':{}}):
                selected=screen.selected_cdr_tracking_screen(d)
            self.assertEqual(selected['selected_tracking_pass'],accepted)


    def test_shared_receiver_uses_selected_sampler_controls_without_timestamp_oracle(self):
        from baseline_envelope import configured_environment,baseline_wired_receiver_inputs
        from wired_envelope import physical_receiver
        design=load_design()
        environment=configured_environment(design.configure(engine='wire',direction='rx',
            reference_hz=2.5e9,host_divider=8))
        resolved=baseline_wired_receiver_inputs(environment,label='shared_receiver_binding')
        controls=resolved['timing_scenario']
        selected=design.architecture['blocks']['cdr']['parameters']
        for key in ('detector_model','phase_gain','frequency_gain','frequency_slope_gain','detector_phase_bins',
                    'detector_phase_span_ui','holdover_residual_ppm'):
            self.assertEqual(controls[key],selected[key])
        self.assertTrue(controls['bound_aperture_motion'])
        cap,tau=resolved['channel_case']
        rx=physical_receiver([0,1]*1000,2.5e9,.1,100.,tau,cap,controls)
        def forbidden(*args):raise AssertionError('Source crossing oracle entered selected detector')
        rx.locate_crossing=forbidden
        for i in range(40):
            rx.forecast(i)
            rx.consume(i)
        self.assertEqual(rx.detector_model,'phase_bank')
        self.assertIsNone(rx.periodic_clock_controller)
        self.assertEqual(controls['acquisition_ui'],1024)
        self.assertFalse(environment['resolved_configuration']['cdr_periodic_tracking'])
        for settings in (dict(engine='rf',direction='rx',sample_divider=64),
                         dict(engine='wire',direction='tx'),
                         dict(engine='wire',direction='rx',wired_pad_path='usb')):
            with self.assertRaisesRegex(ValueError,'serial wired receive'):
                design.configure(reference_hz=2.5e9,cdr_periodic_tracking=True,**settings)

        self.assertEqual(rx.holdover_ui,selected['holdover_bits'])
        # Isolated predictor boundary: constant, already validated feedforward.
        # Local sampled detector noise must still trim phase/frequency, but must
        # not create a second slew estimate to extrapolate through later gaps.
        class ConstantPredictor:
            state='active'
            local_validated=True
            def clone(self):
                import copy
                return copy.copy(self)
            def step(self,*args):return False,1.,0.
            def observe(self,*args):pass
            def period_slew_bound(self):return 0.
        rx.periodic_clock_controller=ConstantPredictor()
        rx.frequency_slope=0.
        rx.frequency_slope_gain=.005
        correction=rx.correction
        for i in range(40,60):
            rx.forecast(i)
            rx.consume(i)
        self.assertEqual(rx.frequency_slope,0.)
        self.assertNotEqual(rx.correction,correction)
        malformed=dict(environment,wired_tracking_sampler_count=3)
        with self.assertRaisesRegex(ValueError,'every sampler slot'):
            baseline_wired_receiver_inputs(malformed,label='missing_sampler')

    def test_cdr_clock_rejections_preserve_supplied_design(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design().hypothetical(reason='CDR package fixture',changes={
            'blocks.power.parameters.shared_return_l_h':.6e-9})
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})) as clock:
            for function in (screen.cdr_tuning_screen,screen.cdr_full_cycle_screen):
                result=function(design.contract,design.architecture,design=design)
                self.assertEqual(result['status'],'clock_rejected')
                self.assertEqual(result['design_provenance'],design.provenance())
                self.assertEqual(result['resolved_configuration']['direction'],'rx')
                self.assertEqual(clock.call_args.args[0]['network']['return_l_h'],.6e-9)

    def test_cdr_candidates_keep_design_context_and_explicit_hypotheses(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        def clock(environment,*args,**kwargs):return environment,{}
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(screen.b,'causal_receiver_envelope',return_value={'independent_fixture':True}) as receiver:
            report=screen.cdr_tuning_screen(design.contract,design.architecture,design=design)
        self.assertEqual(len(report['cases']),12)
        self.assertEqual(receiver.call_count,12)
        self.assertEqual(report['design_provenance'],design.provenance())
        self.assertEqual(report['model_assumptions']['result_role'],'cdr_candidate_comparison')
        self.assertEqual({row['source_slope_ppm_s'] for row in report['cases']},{-300e6,300e6})
        variant=design.hypothetical(reason='CDR sensitivity record propagation',changes={
            'blocks.cdr.parameters.supply_sensitivity_ps_per_mv':.2})
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(screen.b,'causal_receiver_envelope',return_value={'independent_fixture':True,'cases':[]}) as receiver:
            full=screen.cdr_full_cycle_screen(variant.contract,variant.architecture,design=variant,observed_bound=True)
        self.assertEqual(full['design_provenance'],variant.provenance())
        self.assertEqual(full['model_role'],'cdr_requirement_comparison')
        self.assertTrue(all(not row['conditional_acceptance'] for row in full['cases']))
        for row,call in zip(full['cases'],receiver.call_args_list):
            self.assertAlmostEqual(row['local_supply_delay_sensitivity_s_per_v'],
                2e-10*row['aperture_coupling_scale'],places=22)
            actual=call.kwargs['timing_scenarios'][0]
            for key,value in row['diagnostic_intervention']['loop_parameters'].items():
                self.assertEqual(value,actual[key])


class USBPacketSnapshotTests(unittest.TestCase):
    def test_packet_pad_and_exchange_share_snapshot_and_host_clock(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import usb_selected_timing
        design=load_design().hypothetical(reason='USB packet construction variant',changes={
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.,
            'blocks.usbhs.parameters.drive_current_a':.020})
        seen=[]
        def exchange(*,chip,configuration,**kwargs):
            self.assertEqual(configuration.design.provenance(),design.provenance())
            self.assertAlmostEqual(chip.a.h2d_clock_scale*312.5e6,configuration.host_word_hz)
            self.assertAlmostEqual(chip.a.d2h_clock_scale*312.5e6,configuration.host_word_hz)
            self.assertEqual(chip.wired_pad.mode,'usb')
            self.assertEqual(chip.wired_pad.local_passives['term'],(60.,60.))
            self.assertEqual(chip.wired_pad.peer_passives['term'],(45.,45.))
            self.assertEqual(chip.wired_pad.hs_current,.020)
            self.assertEqual(chip.a.startup_s,0.)  # Explicit prequalified fixture.
            seen.append(configuration.record())
            return {'construction_fixture':True}
        with patch.object(usb_selected_timing,'reply_trace',side_effect=exchange):
            result=screen.usb_common_packet_screen(design.contract,design.architecture,design=design)
        self.assertEqual(len(seen),4)
        self.assertTrue(all(config==result['resolved_configuration'] for config in seen))
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertIn('surrogate',result['model_assumptions']['host_current'])


class DiagnosticEnvironmentBindingTests(unittest.TestCase):
    def test_rf_rejects_foreign_configuration_before_waveform_generation(self):
        from unittest.mock import patch
        from baseline_envelope import configured_environment
        import selected_rf
        design=load_design()
        other=design.hypothetical(reason='Foreign RF circuit',changes={
            'blocks.lna.parameters.noise_figure_db':8.})
        for direction,simulate in (('rx',selected_rf.wideband_receive),('tx',selected_rf.wideband_transmit)):
            settings=dict(engine='rf',direction=direction,reference_hz=2.4e9,sample_divider=64,
                **({'pga_gain_db':39} if direction=='rx' else {}))
            environment=configured_environment(design.configure(**settings))
            environment['resolved_configuration']=other.configure(**settings).record()
            with patch.object(selected_rf,'he_source') as waveform:
                with self.assertRaisesRegex(ValueError,'environment design provenance'):
                    simulate(environment)
                waveform.assert_not_called()
            del environment['design_provenance']
            with self.assertRaisesRegex(ValueError,'requires design provenance'):
                simulate(environment)

    def test_rf_results_own_their_recorded_design_and_conditions(self):
        import copy
        from baseline_envelope import configured_environment,wideband_receive,wideband_transmit
        from design_definition import Scenario
        design=load_design()
        scenario=Scenario(assumptions={'temperature_c':25}).override(
            reason='Adverse package fixture',package_return_inductance_h=2e-9)
        keys=('design_provenance','resolved_configuration','scenario_overrides',
              'scenario_assumptions','operating_conditions')
        for direction,simulate in (('rx',wideband_receive),('tx',wideband_transmit)):
            config=design.configure(engine='rf',direction=direction,reference_hz=2.4e9,
                sample_divider=64,**({'pga_gain_db':39} if direction=='rx' else {}))
            environment=configured_environment(config,scenario)
            expected={key:copy.deepcopy(environment[key]) for key in keys}
            result=simulate(environment,oversample=128)
            for key in keys:
                self.assertEqual(result[key],expected[key])
                environment[key].clear()
                self.assertEqual(result[key],expected[key])

    def test_wideband_settling_uses_shared_pga_response(self):
        from baseline_envelope import configured_environment,wideband_receive
        design=load_design().hypothetical(reason='Slower PGA response uncertainty',changes={
            'blocks.pga_i.parameters.gain_response_tau_s':.4e-6,
            'blocks.pga_q.parameters.gain_response_tau_s':.4e-6})
        environment=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        nominal=wideband_receive(environment,oversample=128,gain_initial_db=30.)
        self.assertEqual(nominal['gain_transition']['tau_s'],.4e-6)
        self.assertNotIn('gain_tau_s',nominal['receiver_diagnostic_overrides'])
        from unittest.mock import patch
        for override in ({'gain_tau_s':0.},{'noise_figure_db':9.},
                         {'input_iip3_dbm':-5.},{'adc_enob':9.},{'aperture_rms_s':0.}):
            with self.subTest(override=override), patch('selected_rf.he_source') as source:
                with self.assertRaisesRegex(ValueError,'explicit diagnostic reason'):
                    wideband_receive(environment,**override)
                source.assert_not_called()
        ideal=wideband_receive(environment,oversample=128,gain_initial_db=30.,gain_tau_s=0.,
            diagnostic_reason='Isolate the cost of PGA settling with an instantaneous response')
        self.assertEqual(ideal['result_role'],'receiver_parameter_diagnostic')
        self.assertEqual(ideal['receiver_diagnostic_overrides']['gain_tau_s']['reason'],
            'Isolate the cost of PGA settling with an instantaneous response')
        self.assertEqual(nominal['result_role'],'design_gain_settings')
        self.assertEqual(ideal['gain_transition']['tau_s'],0.)
        self.assertEqual(ideal['receiver_diagnostic_overrides']['gain_tau_s']['selected'],.4e-6)
        self.assertEqual(ideal['receiver_diagnostic_overrides']['gain_tau_s']['diagnostic'],0.)

    def test_receiver_result_retains_clock_diagnostic_identity(self):
        from baseline_envelope import diagnostic_input_environment,wideband_receive
        from design_definition import Scenario
        design=load_design()
        environment=diagnostic_input_environment(design,2.4e9,Scenario(),{'receiver_noise_v':.002})
        result=wideband_receive(environment,oversample=128)
        self.assertEqual(result['diagnostic_input_intervention'],{'receiver_noise_v':.002})
        self.assertEqual(result['diagnostic_input_reason'],environment['diagnostic_input_reason'])
        self.assertEqual(result['design_provenance'],design.provenance())
        result['diagnostic_input_intervention']['receiver_noise_v']=0.
        self.assertEqual(environment['diagnostic_input_intervention']['receiver_noise_v'],.002)

    def test_inventory_rejects_unlabeled_clock_input_changes(self):
        from baseline_envelope import inventory_environment
        design=load_design()
        args=(design.contract,design.architecture,'rf',2.4e9,312.5e6)
        with self.assertRaisesRegex(ValueError,'reasoned diagnostic'):
            inventory_environment(*args,design=design,external_input={'receiver_noise_v':.002})
        result=inventory_environment(*args,design=design,external_input={'receiver_noise_v':.002},
            diagnostic_input_reason='Deliberately adverse receiver-noise fixture')
        self.assertEqual(result['diagnostic_input_intervention'],{'receiver_noise_v':.002})
        self.assertEqual(result['diagnostic_input_reason'],'Deliberately adverse receiver-noise fixture')
        self.assertEqual(result['clock_input_noise_parameters']['receiver_noise_v'],.002)

    def test_clock_intervention_retains_the_same_temperature_and_transport_binding(self):
        from baseline_envelope import configured_environment,diagnostic_input_environment
        from design_definition import Scenario
        design=load_design()
        scenario=Scenario(assumptions={'temperature_c':30})
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=42)
        nominal=configured_environment(config,scenario)
        intervention=diagnostic_input_environment(design,2.4e9,scenario,{'receiver_noise_v':.002})
        for key in ('design_provenance','resolved_configuration','operating_conditions',
                    'scenario_assumptions','scenario_overrides','transport_parameters','converter_parameters'):
            self.assertEqual(intervention[key],nominal[key],key)
        self.assertEqual(intervention['converter_parameters']['temperature_k'],303.15)
        self.assertEqual(intervention['diagnostic_input_intervention'],{'receiver_noise_v':.002})
        self.assertEqual(intervention['clock_input_noise_parameters']['receiver_noise_v'],.002)
        from selected_lifecycle import continuation_context
        replay=continuation_context(design,{'clock':intervention})
        captured=replay['input_capture_context']['clock']
        self.assertEqual(captured['diagnostic_input_intervention'],{'receiver_noise_v':.002})
        self.assertEqual(captured['diagnostic_input_reason'],'Explicit clock-input contribution isolation')
        self.assertEqual(captured['resolved_configuration'],config.record())
        captured['diagnostic_input_intervention']['receiver_noise_v']=0.
        self.assertEqual(intervention['diagnostic_input_intervention']['receiver_noise_v'],.002)


class ReferenceAcceptanceSnapshotTests(unittest.TestCase):
    def test_shared_source_skew_reaches_driven_input_and_nodal_control(self):
        import numpy as np
        from baseline_envelope import configured_environment
        from reference_input_probe import paired_environment,full,reference_passive_parameters
        base=load_design();contract=base.contract
        contract['physical_services']['external_clock_input']['source_leg_skew_s']=40e-12
        design=DesignDefinition.from_documents(contract,base.architecture)
        environment=configured_environment(design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8))
        opts=contract['physical_services']['external_clock_input']['input_model']
        delivered,report=paired_environment(environment,opts)
        self.assertIsNotNone(delivered)
        self.assertEqual(report['source_leg_skew_s'],40e-12)
        nodes,_,_=full(2.5e9,environment['network'],np.zeros(5),1.,opts['mismatch'],opts['opposed'],
            source_skew_s=40e-12,**reference_passive_parameters(environment))
        local=nodes[5:]-nodes[3]
        expected=local[0]-local[1]+opts['cm_gain']*np.mean(local)
        self.assertAlmostEqual(abs(delivered['reference_threshold']['carrier_v']-expected),0.,places=12)
        from reference_input_probe import environment_port
        response=environment_port(2.5e9,environment,np.zeros(5),source_diff=1.,**opts)
        self.assertAlmostEqual(abs(response['effective']-expected),0.,places=12)
        missing=dict(environment);del missing['reference_pad_parameters']
        with self.assertRaises(ValueError):environment_port(2.5e9,missing,np.zeros(5),**opts)

        del contract['physical_services']['external_clock_input']['source_leg_skew_s']
        with self.assertRaises(ValueError):DesignDefinition.from_documents(contract,base.architecture)

    def test_reference_source_amplitude_has_one_owner_and_reaches_clock_path(self):
        from baseline_envelope import configured_environment,reference_payload_environment
        design=load_design();architecture=design.architecture
        architecture['blocks']['refpad']['parameters']['source_differential_peak_v']=1.
        with self.assertRaisesRegex(ValueError,'Duplicate reference source amplitude'):
            DesignDefinition.from_documents(design.contract,architecture)
        contract=design.contract;contract['physical_services']['external_clock_input']['source_differential_peak_v']=.75
        selected=DesignDefinition.from_documents(contract,design.architecture)
        environment=configured_environment(selected.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8))
        delivered,report=reference_payload_environment(environment,{'link_r_ohm':1e-5},False)
        self.assertIsNotNone(delivered)
        self.assertEqual(report['physical_source_peak_v'],.75)
        self.assertEqual(delivered['external_clock_input']['physical_source_peak_v'],.75)
        from reference_input_probe import differential_source_peak,paired_input_envelope,paired_environment
        opts=environment['clock_input_configuration']['input_model']
        self.assertEqual(differential_source_peak(environment),.75)
        self.assertEqual(differential_source_peak(environment,.5),.5)
        self.assertEqual(differential_source_peak({}),1.)
        _,direct=paired_environment(environment,opts)
        self.assertEqual(direct['source_differential_peak_v'],.75)
        envelope=paired_input_envelope(environment,opts,source_peak_v=.5)
        self.assertEqual(envelope['source_differential_peak_v'],.5)
        for record in (direct,envelope):
            self.assertEqual(record['design_provenance'],selected.provenance())
            self.assertEqual(record['resolved_configuration'],environment['resolved_configuration'])
            record['design_provenance']['documents'].clear()
            record['resolved_configuration']['reference_hz']=1.
        self.assertEqual(environment['design_provenance'],selected.provenance())
        self.assertEqual(environment['resolved_configuration']['reference_hz'],2.5e9)
        missing=dict(environment);del missing['clock_input_configuration']
        for helper in (paired_environment,paired_input_envelope):
            with self.assertRaisesRegex(ValueError,'requires source amplitude'):
                helper(missing,opts,source_peak_v=.5)
        for invalid in (0.,-1.,True,float('nan')):
            with self.assertRaises(ValueError):
                differential_source_peak(environment,invalid)
        for invalid in (0.,-1.,True,float('nan')):
            contract=design.contract
            contract['physical_services']['external_clock_input']['source_differential_peak_v']=invalid
            with self.assertRaises(ValueError):
                DesignDefinition.from_documents(contract,design.architecture)

    def test_missing_acceptance_and_incompatible_threshold_fail(self):
        from baseline_envelope import configured_environment
        from selected_rf import reference_acceptance_parameters
        design=load_design()
        for key in ('threshold_v','effective_peak_limit_v','leg_peak_limit_v'):
            architecture=design.architecture
            del architecture['model_assumptions']['reference_input_acceptance']['parameters'][key]
            with self.assertRaisesRegex(ValueError,'Complete reference input acceptance'):
                DesignDefinition.from_documents(design.contract,architecture)
        with self.assertRaisesRegex(ValueError,'inside effective input envelope'):
            design.hypothetical(reason='Invalid acceptance experiment',changes={
                'model_assumptions.reference_input_acceptance.parameters.threshold_v':.7})
        environment=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.426e9,sample_divider=64,pga_gain_db=39))
        del environment['reference_acceptance_parameters']
        with self.assertRaisesRegex(ValueError,'requires acceptance parameters'):
            reference_acceptance_parameters(environment)
        self.assertEqual(reference_acceptance_parameters({})['leg_peak_limit_v'],.6)
        from selected_rf import (clock_supply_sensitivity,clock_supply_delay_pole,
                                 reference_supply_parameters)
        helpers=(reference_acceptance_parameters,clock_supply_sensitivity,
                 clock_supply_delay_pole,reference_supply_parameters)
        for helper in helpers:
            for marker in ('design_provenance','inventory_current_report','resolved_configuration'):
                with self.subTest(helper=helper.__name__,marker=marker),self.assertRaises(ValueError):
                    helper({marker:environment[marker]})
        self.assertEqual(clock_supply_sensitivity({}),.1)
        self.assertEqual(clock_supply_delay_pole({}),1e9)
        self.assertEqual(reference_supply_parameters({})['supply_pole_hz'],10e6)

    def test_changed_limits_reach_seed_and_independent_crossing_equation(self):
        import numpy as np
        from baseline_envelope import configured_environment,reference_edge_screen
        from selected_rf import reference_acceptance_parameters
        design=load_design().hypothetical(reason='Assigned reference acceptance experiment',changes={
            'model_assumptions.reference_input_acceptance.parameters.threshold_v':.03,
            'model_assumptions.reference_input_acceptance.parameters.effective_peak_limit_v':.7,
            'model_assumptions.reference_input_acceptance.parameters.leg_peak_limit_v':1e-6})
        environment=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.426e9,sample_divider=64,pga_gain_db=39))
        self.assertEqual(environment['external_clock_input']['threshold_v'],.03)
        self.assertEqual(environment['external_clock_input']['peak_limit_v'],.7)
        parameters=reference_acceptance_parameters(environment)
        f=2e9;carrier=.2;perturb=.04j
        result=reference_edge_screen(f,carrier,[(f,perturb)],threshold_v=parameters['threshold_v'],
            peak_limit_v=parameters['effective_peak_limit_v'])
        expected=(np.arcsin(.03/abs(carrier+perturb))-np.angle(carrier+perturb)-np.arcsin(.03/carrier))/(2*np.pi*f)
        self.assertAlmostEqual(result['static_mean_edge_shift_ps'],expected*1e12,places=7)
        self.assertTrue(result['incremental_envelope_met'])
        from reference_input_probe import paired_environment
        paired,report=paired_environment(environment,design.contract['physical_services']['external_clock_input']['input_model'])
        self.assertIsNone(paired)
        self.assertEqual(report['design_provenance'],design.provenance())
        self.assertEqual(report['resolved_configuration'],environment['resolved_configuration'])
        self.assertFalse(report['acceptance_checks']['individual_leg_envelope'])
        self.assertEqual(report['clock']['threshold_v'],.03)
        self.assertEqual(report['clock']['peak_limit_v'],.7)
        self.assertEqual(report['reference_acceptance_parameters']['leg_peak_limit_v'],1e-6)


class ReferenceSupplySnapshotTests(unittest.TestCase):
    def test_paired_clock_validates_noise_before_simulation(self):
        from baseline_envelope import configured_environment
        from reference_input_probe import paired_environment
        from unittest.mock import patch
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=64,pga_gain_db=39)
        environment=configured_environment(config)
        noise=environment['clock_input_noise_parameters']
        malformed=[None,{},dict(noise,unowned_parameter=1.)]
        malformed.extend({key:value for key,value in noise.items() if key!=missing}
                         for missing in noise)
        malformed.extend(dict(noise,receiver_noise_v=value)
                         for value in (-1.,float('nan'),True,'quiet'))
        with patch('reference_input_probe.port') as solver:
            for parameters in malformed:
                with self.subTest(parameters=parameters):
                    with self.assertRaisesRegex(ValueError,'clock noise parameters'):
                        paired_environment(dict(environment,clock_input_noise_parameters=parameters),{})
            # Even a legacy inventory-bound environment cannot fall back to primitive noise.
            legacy=dict(environment);del legacy['design_provenance'];del legacy['clock_input_noise_parameters']
            with self.assertRaisesRegex(ValueError,'clock noise parameters'):
                paired_environment(legacy,{})
            solver.assert_not_called()

    def test_ble_entry_points_reject_missing_or_foreign_configuration(self):
        from baseline_envelope import configured_environment
        from ble_packet import joined_scan_request,transmitted_scan_response
        import copy
        design=load_design()
        for direction in ('rx','tx'):
            config=design.configure(engine='rf',direction=direction,reference_hz=2.426e9,
                sample_divider=64,**({'pga_gain_db':39} if direction=='rx' else {}))
            environment=configured_environment(config)
            def invoke(value):
                if direction=='rx':return joined_scan_request(value,design.contract)
                return transmitted_scan_response({},value,design.contract)
            missing=copy.deepcopy(environment);del missing['resolved_configuration']
            with self.assertRaisesRegex(ValueError,'requires a resolved configuration'):
                invoke(missing)
            foreign=copy.deepcopy(environment)
            foreign['resolved_configuration']['design_fingerprint']='different-snapshot'
            with self.assertRaisesRegex(ValueError,'conflicts with environment design provenance'):
                invoke(foreign)
            missing=copy.deepcopy(environment);del missing['design_provenance']
            with self.assertRaisesRegex(ValueError,'requires design provenance'):
                invoke(missing)

    def test_partial_bound_converter_cannot_inherit_primitive_defaults(self):
        from baseline_envelope import configured_environment,environment_converter_parameters
        design=load_design().hypothetical(reason='Reference reservoir experiment',changes={
            'blocks.refbuf.parameters.reservoir_f':200e-12})
        environment=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        self.assertEqual(environment_converter_parameters(environment).reference_cap_f,200e-12)
        for key in ('reference_cap_f','bit_durations_s'):
            partial=dict(environment['converter_parameters']);del partial[key]
            with self.assertRaisesRegex(ValueError,'complete converter parameters'):
                environment_converter_parameters(dict(environment,converter_parameters=partial))
        self.assertEqual(environment_converter_parameters({'converter_parameters':{'reference_cap_f':150e-12}}).reference_cap_f,150e-12)
        import baseline_envelope as b
        # Any retained chip-identity marker forbids silently downgrading a
        # damaged environment to an independent mathematical fixture.
        consumers=(
            ('converter',lambda e:b.environment_converter_parameters(e)),
            ('partial_converter',lambda e:b.environment_converter_parameters(dict(e,converter_parameters={}))),
            ('receiver',lambda e:b.receiver_inventory_options(e,architecture=design.architecture)),
            ('wired_gain',lambda e:b.wired_gain_reference(e)),
            ('wired_delay',lambda e:b.wired_shared_impairment(dict(e,payload_engine='wire',
                ledger={'local_payload_clock_core_rail_v':3.3},host_spectrum={'tones':[]}))),
            ('feedback',lambda e:b.reference_feedback_response({'reference_limit_a':.001},e)),
            ('host_source',lambda e:b.host_source_parameters(dict(e,host_spectrum={}))))
        for marker in ('design_provenance','inventory_current_report','resolved_configuration'):
            for name,consume in consumers:
                with self.subTest(marker=marker,consumer=name),self.assertRaises(ValueError):
                    consume({marker:environment[marker]})
        self.assertEqual(b.wired_gain_reference({}),3.3)
        self.assertEqual(b.environment_converter_parameters({}),b.SARParameters())

        import ble_packet as packet
        import reference_input_probe as reference
        import converter_dynamics as converter
        consumers=(packet.receiver_lna_gain,packet.receiver_pga_peak,
                   packet.receiver_pga_response,packet.packet_driver_bias,
                   packet.packet_dac_settings,reference.reference_capacitance,
                   reference.reference_passive_parameters,converter.reference_load_parameters,
                   reference.differential_source_peak)
        for marker in ('design_provenance','inventory_current_report','resolved_configuration'):
            marked={marker:environment[marker]}
            for consume in consumers:
                with self.subTest(marker=marker,consumer=consume.__name__),self.assertRaises(ValueError):
                    consume(marked)
            with self.assertRaisesRegex(ValueError,'complete converter parameters'):
                converter.validate_sar_binding(marked,converter.SARParameters())
            with self.assertRaisesRegex(ValueError,'source leg skew'):
                reference.reference_source_skew(marked,0.)
            # A complete SAR schedule cannot excuse absent aperture noise.
            marked.update(converter_parameters=environment['converter_parameters'],carrier_hz=2.4e9)
            parameters=b.environment_converter_parameters(marked)
            with self.assertRaisesRegex(ValueError,'ADC aperture parameters'):
                converter.tone_precision(marked,parameters,count=16,bin_number=3)
        self.assertEqual(packet.receiver_lna_gain({}),20.)
        self.assertEqual(packet.receiver_pga_peak({}),.8)
        self.assertEqual(packet.receiver_pga_response({}),.2e-6)
        self.assertEqual(packet.packet_driver_bias({}),.028)
        self.assertEqual(packet.packet_dac_settings({})[0]['converter_bits'],12)
        self.assertEqual(packet.packet_dac_settings({},converter_bits=10)[0]['converter_bits'],10)
        tx=configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=64))
        rx=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.426e9,sample_divider=64,pga_gain_db=39))
        from unittest.mock import patch
        with patch('ble_packet.gfsk') as source:
            with self.assertRaisesRegex(ValueError,'ADC native width requires a changed design'):
                packet.joined_scan_request(rx,design.contract,converter_bits=12)
            with self.assertRaisesRegex(ValueError,'DAC native width requires a changed design'):
                packet.transmitted_scan_response({},tx,design.contract,converter_bits=12)
            for width in (10.,True):
                with self.assertRaises(ValueError):packet.packet_dac_settings(tx,converter_bits=width)
                with self.assertRaises(ValueError):packet.joined_scan_request(rx,design.contract,converter_bits=width)
            source.assert_not_called()
        alternate=design.hypothetical(reason='Explicit wider packet DAC experiment',changes={
            'blocks.dac_i.parameters.native_bits':12,'blocks.dac_q.parameters.native_bits':12})
        alternative=configured_environment(alternate.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=64))
        rejected=packet.transmitted_scan_response({'response':{'reply_armed':False}},alternative,design.contract)
        self.assertEqual(rejected['dac_settings']['converter_bits'],12)
        self.assertEqual(rejected['design_provenance'],alternate.provenance())
        self.assertEqual(rejected['dac_diagnostic_overrides'],{})

        self.assertEqual(reference.reference_capacitance({}),3e-12)
        self.assertEqual(reference.reference_passive_parameters({})['bond_l_h'],2e-9)
        converter.validate_sar_binding({},converter.SARParameters())


    def test_reference_probe_manifest_detects_source_drift(self):
        from reference_input_probe import probe_source_hashes,verify_probe_sources
        hashes=probe_source_hashes()
        for name in ('spec/contract.json','spec/analog-architecture.json',
                     'system_model/architecture_fast/design_definition.py',
                     'verification/reference_input_probe.py','verification/wideband_packet.py',
                     'verification/selected_lifecycle.py','verification/usb_selected_timing.py',
                     'system_model/architecture_fast/direct_stream.py'):
            self.assertIn(name,hashes)
        verify_probe_sources(hashes)
        changed=dict(hashes)
        changed['verification/reference_input_probe.py']='0'*64
        with self.assertRaisesRegex(RuntimeError,'Sources changed'):
            verify_probe_sources(changed)

    def test_reference_package_boundary_rejects_missing_and_nonpassive_values(self):
        from reference_input_probe import port,full,package_descriptor,reference_passive_parameters
        from baseline_envelope import clock_screen_environment
        design=load_design()
        for key in ('bond_l_h','source_r_ohm','mutual_l_h'):
            architecture=design.architecture
            del architecture['model_assumptions']['reference_input_package']['parameters'][key]
            with self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        package=environment['reference_package_parameters']
        for key in package:
            incomplete=dict(package)
            del incomplete[key]
            with self.subTest(missing_package_field=key):
                with self.assertRaisesRegex(ValueError,'complete package parameters'):
                    reference_passive_parameters(dict(environment,reference_package_parameters=incomplete))
        for invalid in (dict(package,unowned_parameter=1.),[],42):
            with self.assertRaisesRegex(ValueError,'complete package parameters'):
                reference_passive_parameters(dict(environment,reference_package_parameters=invalid))
        del environment['reference_package_parameters']
        with self.assertRaisesRegex(ValueError,'requires package parameters'):
            reference_passive_parameters(environment)
        # Positive individual inductances do not guarantee a passive coupled pair.
        options=dict(mismatch=.2,mutual_l_h=1.99e-9)
        for evaluate in (
            lambda:port(1e9,environment['network'],[0]*5,**options),
            lambda:full(1e9,environment['network'],[0]*5,0.,.2,False,mutual_l_h=1.99e-9),
            lambda:package_descriptor(environment['network'],**options)):
            with self.assertRaisesRegex(ValueError,'positive definite'):
                evaluate()

    def test_reference_package_variant_reaches_transfer_and_modes(self):
        from baseline_envelope import clock_screen_environment
        from reference_input_probe import reference_passive_parameters,port,full
        from converter_dynamics import native_load_modes
        import numpy as np
        design=load_design().hypothetical(reason='Reference signal package uncertainty',changes={
            'model_assumptions.reference_input_package.parameters.bond_l_h':3e-9,
            'model_assumptions.reference_input_package.parameters.source_r_ohm':75.,
            'model_assumptions.reference_input_package.parameters.mutual_l_h':.2e-9})
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        parameters=reference_passive_parameters(environment);w=2*np.pi*1e9
        actual=port(1e9,environment['network'],np.zeros(5),source_diff=.7,**parameters)
        expected=.7/(1+1j*w*75*2.7e-12-w*w*(3e-9-.2e-9)*2.7e-12)
        self.assertAlmostEqual(complex(actual['effective']),complex(expected),places=12)
        environment['reference_load_parameters']=dict(differential=dict(mismatch=0.,opposed=False,cm_gain=.1))
        poles,fields,_=native_load_modes(environment)
        direct,residues=fields['rail_v']
        modal=direct+np.sum(residues/(1j*w-poles))
        nodes,_,_=full(1e9,environment['network'],[0,-1,0,1,0],0.,0.,False,**parameters)
        expected=(nodes[1]-nodes[3])/(1+1j*w*.2e-9)
        np.testing.assert_allclose(modal,expected,rtol=1e-8,atol=1e-10)

    def test_feedback_and_wake_reject_unowned_pad_loading(self):
        from baseline_envelope import clock_screen_environment,reference_feedback_response
        from selected_rf import driver_wake_response
        design=load_design()
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        environment.update(local_supply_sensitivity_ps_per_mv=.025,local_supply_delay_sign=1.,
            periodic_clock={},reference_load_parameters=dict(cap_f=3e-12,differential=
                design.contract['physical_services']['external_clock_input']['input_model']))
        with self.assertRaisesRegex(ValueError,'conflicts with shared pad'):
            reference_feedback_response({'reference_limit_a':.001},environment)
        with self.assertRaisesRegex(ValueError,'conflicts with shared pad'):
            driver_wake_response(environment,released_current_a=.001,wake_start_s=1e-6)

    def test_reference_pad_capacitance_reaches_passive_solvers(self):
        from baseline_envelope import clock_screen_environment
        from reference_input_probe import port,full,package_descriptor,reference_capacitance
        from converter_dynamics import native_load_modes
        import numpy as np
        design=load_design().hypothetical(reason='Reference pad loading experiment',changes={
            'blocks.refpad.parameters.capacitance_f_per_leg':4.1e-12})
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        cap=reference_capacitance(environment)
        self.assertEqual(cap,4.1e-12)
        network=environment['network'];frequency=1e9;w=2*np.pi*frequency
        reduced=port(frequency,network,np.zeros(5),source_diff=.7,cap_f=cap)
        expected=.7/(1+1j*w*50.2*cap-w*w*(2e-9-.4e-9)*cap)
        self.assertAlmostEqual(complex(reduced['effective']),complex(expected),places=12)
        nodes,_,_=full(frequency,network,np.zeros(5),.7,0.,False,cap_f=cap)
        E,G,F=package_descriptor(network,cap_f=cap)
        state=np.linalg.solve(1j*w*E+G,F@np.r_[np.zeros(5),.35,-.35])
        np.testing.assert_allclose(state[:7],nodes,rtol=1e-9,atol=1e-12)
        self.assertAlmostEqual(complex(state[5]-state[6]),complex(expected),places=12)
        environment['reference_load_parameters']=dict(cap_f=3e-12,differential=
            design.contract['physical_services']['external_clock_input']['input_model'])
        with self.assertRaisesRegex(ValueError,'conflicts with shared pad'):
            native_load_modes(environment)
        del environment['reference_pad_parameters']
        with self.assertRaisesRegex(ValueError,'requires pad parameters'):
            reference_capacitance(environment)

    def test_raw_seed_uses_contract_clock_sensitivity(self):
        from baseline_envelope import clock_screen_environment
        from converter_dynamics import native_load_modes
        from selected_rf import clock_supply_sensitivity
        import numpy as np
        base=load_design();contract=base.contract
        contract['physical_services']['external_clock_input']['supply_sensitivity_ps_per_mv']=.037
        design=DesignDefinition.from_documents(contract,base.architecture)
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        self.assertNotIn('local_supply_sensitivity_ps_per_mv',environment)
        from reference_input_probe import paired_environment
        paired,report=paired_environment(environment,contract['physical_services']['external_clock_input']['input_model'])
        self.assertEqual(paired['local_supply_sensitivity_ps_per_mv'],.037)
        self.assertEqual(report['sensitivity_ps_per_mv'],.037)
        self.assertEqual(report['supply_delay_pole_hz'],1e9)
        self.assertEqual(report['capacitance_f_per_leg'],2.7e-12)
        environment['reference_load_parameters']=dict(differential=
            contract['physical_services']['external_clock_input']['input_model'])
        poles,fields,_=native_load_modes(environment)
        z=2j*np.pi*1e9
        direct,residues=fields['rail_v'];rail=direct+np.sum(residues/(z-poles))
        direct,residues=fields['delay_s']
        delay=direct+np.sum(residues/(z-np.r_[poles,-2*np.pi*1e9]))
        np.testing.assert_allclose(delay/rail,.037e-9/(1+1j),rtol=1e-10,atol=1e-25)
        self.assertEqual(clock_supply_sensitivity(dict(environment,local_supply_sensitivity_ps_per_mv=.2)),.2)
        self.assertEqual(clock_supply_sensitivity({}),.1)
        del environment['clock_input_configuration']
        with self.assertRaisesRegex(ValueError,'requires supply delay'):
            clock_supply_sensitivity(environment)

    def test_shared_clock_pole_reaches_native_transfer(self):
        from baseline_envelope import clock_screen_environment
        from converter_dynamics import native_load_modes
        from selected_rf import clock_supply_delay_pole
        import numpy as np
        base=load_design();contract=base.contract
        contract['physical_services']['external_clock_input']['supply_delay_pole_hz']=200e6
        design=DesignDefinition.from_documents(contract,base.architecture)
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        environment['reference_load_parameters']=dict(differential=
            contract['physical_services']['external_clock_input']['input_model'])
        from reference_input_probe import paired_environment
        environment,_=paired_environment(environment,environment['reference_load_parameters']['differential'],
            sensitivity_ps_per_mv=contract['physical_services']['external_clock_input']['supply_sensitivity_ps_per_mv'])
        poles,fields,_=native_load_modes(environment)
        gain=environment['local_supply_sensitivity_ps_per_mv']*1e-9*environment['local_supply_delay_sign']
        for frequency in (20e6,200e6,2e9):
            z=2j*np.pi*frequency
            direct,residues=fields['rail_v'];rail=direct+np.sum(residues/(z-poles))
            direct,residues=fields['delay_s']
            delay=direct+np.sum(residues/(z-np.r_[poles,-2*np.pi*200e6]))
            np.testing.assert_allclose(delay/rail,gain/(1+1j*frequency/200e6),rtol=1e-10,atol=1e-25)
        del environment['clock_input_configuration']
        with self.assertRaisesRegex(ValueError,'requires supply delay'):
            native_load_modes(environment)
        self.assertEqual(clock_supply_delay_pole({}),1e9)
        for bad in (0,-1,True,float('inf')):
            contract['physical_services']['external_clock_input']['supply_delay_pole_hz']=bad
            with self.assertRaisesRegex(ValueError,'clock supply delay pole|finite JSON'):
                DesignDefinition.from_documents(contract,base.architecture)

    def test_native_reference_transfer_and_state_follow_shared_law(self):
        from baseline_envelope import clock_screen_environment
        from converter_dynamics import native_load_modes,sampled_load_response
        import numpy as np
        design=load_design().hypothetical(reason='Native reference response experiment',changes={
            'blocks.refbuf.parameters.supply_fraction_per_v':.2,
            'blocks.refbuf.parameters.supply_pole_hz':5e6})
        environment,_=clock_screen_environment(design,'rf',2.426e9)
        environment['reference_load_parameters']=dict(differential=
            design.contract['physical_services']['external_clock_input']['input_model'])
        poles,fields,_=native_load_modes(environment)
        for frequency in (1e6,5e6,30e6):
            z=2j*np.pi*frequency
            direct,residues=fields['rail_v']
            rail=direct+np.sum(residues/(z-poles))
            direct,residues=fields['reference_fraction']
            reference=direct+np.sum(residues/(z-np.r_[poles,-2*np.pi*5e6]))
            self.assertAlmostEqual(complex(reference/rail),complex(.2/(1+1j*frequency/5e6)),places=11)
        times=np.arange(100)*1e-9
        first,_=sampled_load_response(times,np.full(100,.001),environment,guard_s=20e-9)
        changed=dict(environment,reference_supply_parameters=dict(supply_fraction_per_v=.3,supply_pole_hz=5e6))
        with self.assertRaisesRegex(ValueError,'does not match'):
            sampled_load_response(times+100e-9,np.zeros(100),changed,
                initial_state=first['final_state'],guard_s=20e-9)
        del environment['reference_supply_parameters']
        for method in ('native_modal','coarse_fft'):
            with self.assertRaisesRegex(ValueError,'requires supply coupling'):
                sampled_load_response(times,np.zeros(100),environment,method=method)

    def test_stopped_clock_forcing_removes_changed_d2h_current(self):
        import numpy as np
        from selected_lifecycle import full_package_handover
        base=load_design();captures=[]
        for charge in (0.,14e-12):
            design=base.hypothetical(reason='Stopped-clock charge partition',changes={
                'model_assumptions.host_switching.parameters.d2h_internal_charge_c':charge})
            capture={}
            full_package_handover(design.contract,design=design,capture=capture,rf_retune=True)
            captures.append(capture['clock_forcing'])
        # The retained H2D/core forcing must not inherit D2H charge changes.
        for frequency in set(captures[0]['off'])|set(captures[1]['off']):
            if frequency==0.:continue  # DC ledger is checked separately.
            np.testing.assert_allclose(captures[0]['off'].get(frequency,np.zeros(7)),
                captures[1]['off'].get(frequency,np.zeros(7)),atol=1e-15,rtol=1e-12)
        self.assertTrue(any(np.max(abs(captures[0]['on'].get(f,np.zeros(7))-
            captures[1]['on'].get(f,np.zeros(7))))>1e-6 for f in captures[0]['on'] if f))

    def test_package_handover_uses_shared_reference_gain_and_pole(self):
        from selected_lifecycle import full_package_handover
        import numpy as np
        design=load_design().hypothetical(reason='Lifecycle reference rejection experiment',changes={
            'blocks.refbuf.parameters.supply_fraction_per_v':.2,
            'blocks.refbuf.parameters.supply_pole_hz':5e6})
        capture={}
        from unittest.mock import patch
        from baseline_envelope import configured_environment
        # A legal slower sample setting must survive into retained ADC forcing.
        def slower_endpoint(design,mode,carrier):
            self.assertEqual(mode,'rf')
            return configured_environment(design.configure(engine=mode,direction='rx',
                reference_hz=carrier,sample_divider=128,pga_gain_db=42))
        from selected_lifecycle import handover_environment
        def endpoint(design,mode,carrier):
            return (slower_endpoint(design,mode,carrier) if mode=='rf' else
                    handover_environment(design,mode,carrier))
        with patch('selected_lifecycle.handover_environment',side_effect=endpoint):
            full_package_handover(design.contract,design=design,capture=capture,
                rf_retune=True,adc_current_a=.001)
        self.assertAlmostEqual(min(capture['clock_forcing']['adc']),2.484e9/128)
        self.assertEqual(capture['environment_conditions'][-1]['adc_switching'],
            dict(sample_hz=2.484e9/128,mean_a=.001,pulse_tau_s=.2e-9,harmonics=128))
        dt=np.diff(capture['times_s'])
        alpha=np.exp(-2*np.pi*5e6*dt)
        ripple=capture['rail_v']-capture['clock_forcing']['dc_rail_v']
        fractional=capture['reference_v']-1.
        expected=alpha*fractional[:-1]+(1-alpha)*.2*ripple[1:]
        np.testing.assert_allclose(fractional[1:],expected,rtol=0.,atol=5e-16)
        self.assertEqual(capture['design_provenance'],design.provenance())
        from selected_lifecycle import package_clock_loss
        # Observe the actual monitor input after the package transient solver.
        with patch('behavioral.ReferencePresence',side_effect=RuntimeError('monitor input captured')) as monitor:
            with self.assertRaisesRegex(RuntimeError,'monitor input captured'):
                package_clock_loss(design.contract,capture,design=design)
        observed=monitor.call_args.args[0]
        np.testing.assert_allclose(np.diff(observed[:5]),128/2.484e9,rtol=0.,atol=1e-18)

    def test_reference_law_reaches_seed_and_complex_transfer(self):
        from baseline_envelope import configured_environment
        from selected_rf import reference_supply_transfer
        import numpy as np
        design=load_design().hypothetical(reason='Reference supply rejection uncertainty',changes={
            'blocks.refbuf.parameters.supply_fraction_per_v':.2,
            'blocks.refbuf.parameters.supply_pole_hz':5e6})
        environment=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        f=5e6
        self.assertAlmostEqual(complex(reference_supply_transfer(environment,f)),.1-.1j)
        rail={tone['frequency_hz']:tone for tone in environment['host_spectrum']['tones']}
        for frequency,amplitude,phase in environment['reference_fraction_tones']:
            source=rail[frequency]
            expected=source['clock_rail_voltage_peak_v']*np.exp(1j*source['voltage_phase_rad'])*.2/(1+1j*frequency/5e6)
            self.assertAlmostEqual(complex(amplitude*np.exp(1j*phase)),complex(expected))
        del environment['reference_supply_parameters']
        with self.assertRaisesRegex(ValueError,'requires supply coupling'):
            reference_supply_transfer(environment,f)
        self.assertAlmostEqual(complex(reference_supply_transfer({},10e6)),.05-.05j)


class FilterBudgetSnapshotTests(unittest.TestCase):
    def test_five_pole_transmitter_reaches_wifi_lifecycle_and_history_bound(self):
        import numpy as np
        from unittest.mock import patch
        from selected_revision_check import five_pole_tx_candidate
        from selected_lifecycle import lifecycle_tx_filter,lifecycle_filter_settings
        from selected_rf import tx_amplitude_bound
        from wifi_client_exchange import ClientBench,analog_hold_at
        selected=load_design()
        design=five_pole_tx_candidate(selected)
        self.assertEqual(design.fingerprint,selected.fingerprint)
        self.assertEqual(five_pole_tx_candidate(design).fingerprint,design.fingerprint)
        family,order=lifecycle_tx_filter(design)
        self.assertEqual(order,5)
        self.assertEqual(lifecycle_filter_settings(design)['tx_cutoff_hz'],12e6)
        bench=ClientBench(design=design)
        with patch('wifi_client_exchange.analog_hold_at',wraps=analog_hold_at) as held:
            bench.rf.process(np.zeros(64,complex),'idle')
        self.assertEqual(held.call_args.kwargs['family'],family)
        self.assertEqual(held.call_args.kwargs['cutoff_hz'],12e6)
        requirement=design.contract['generic_configuration_target']['tx_amplitude_operating_requirement']
        bounds=[tx_amplitude_bound(requirement,reconstruction_family=prototype)
                for prototype in ('tx_third_order',family)]
        self.assertNotEqual(bounds[0]['reconstruction_l1_upper_bound'],bounds[1]['reconstruction_l1_upper_bound'])
        self.assertEqual(bounds[1]['reconstruction_family'],family)
        self.assertLess(bounds[1]['sufficient_native_complex_code_radius'],bounds[0]['sufficient_native_complex_code_radius'])

    def test_wifi_filters_follow_snapshot_and_reject_illegal_mutation(self):
        import numpy as np
        from unittest.mock import patch
        from wifi_client_exchange import ClientBench,SharedRFPath,analog_filter,analog_hold_at
        design=load_design().hypothetical(reason='Wi-Fi paired filter allocation',changes={
            'blocks.rxfilter_q.parameters.cutoff_hz':[100000.,8e6],
            'blocks.txfilter_i.parameters.cutoff_hz':[100000.,10e6]})
        bench=ClientBench(design=design)
        for source in (bench.rf.filter_settings(),bench.chip.resources):
            self.assertEqual(source['rx_cutoff_hz'],8e6)
            self.assertEqual(source['tx_cutoff_hz'],10e6)
        with patch('wifi_client_exchange.analog_filter',wraps=analog_filter) as rx:
            bench.rf.process(np.zeros(64,complex),'rx')
            self.assertEqual(rx.call_args.kwargs['cutoff_hz'],8e6)
        with patch('wifi_client_exchange.analog_hold_at',wraps=analog_hold_at) as tx:
            bench.rf.process(np.zeros(64,complex),'idle')
            self.assertEqual(tx.call_args.kwargs['cutoff_hz'],10e6)
        before=bench.rf.time
        bench.rf.rx_cutoff_hz=9e6
        with self.assertRaisesRegex(ValueError,'shared paired rx range'):
            bench.rf.process(np.zeros(64,complex),'rx')
        self.assertEqual(bench.rf.time,before)
        with self.assertRaisesRegex(ValueError,'shared paired rx range'):
            bench.context_record()
        # Independent mathematical examples retain their own range choices.
        primitive=SharedRFPath();primitive.rx_cutoff_hz=10.5e6
        self.assertEqual(primitive.filter_settings()['rx_cutoff_hz'],10.5e6)

    def test_blocker_bandwidth_expansion_has_hypothetical_identity(self):
        from unittest.mock import patch
        from wifi_client_exchange import modulated_blocker_screen
        design=load_design()
        # Isolate campaign construction/provenance from costly packet decoding.
        with patch('wifi_client_exchange.ClientBench.receive_intent',side_effect=ValueError('fixture decode')):
            report=modulated_blocker_screen(design=design)
        for row in report['rows']:
            provenance=row['design_provenance']
            if row['cutoff_hz']==9.53125e6:
                self.assertEqual(provenance['design_fingerprint'],design.fingerprint)
            else:
                self.assertNotEqual(provenance['design_fingerprint'],design.fingerprint)
                experiment=provenance['circuit_experiments'][-1]
                self.assertEqual(experiment['parent_design_fingerprint'],design.fingerprint)
                self.assertEqual({change['path'] for change in experiment['changes']},
                    {'blocks.rxfilter_i.parameters.cutoff_hz','blocks.rxfilter_q.parameters.cutoff_hz'})
            self.assertEqual(row['resolved_configuration']['design_fingerprint'],provenance['design_fingerprint'])

    def test_changed_filter_shapes_are_rejected_instead_of_ignored(self):
        from selected_lifecycle import lifecycle_filter_settings
        design=load_design()
        for parameter,value in (('blocks.txfilter_i.parameters.stage_q',[.7,1.618033988749895]),
                                ('blocks.txfilter_q.parameters.gain',2.),
                                ('blocks.rxfilter_q.parameters.default_response','different prototype')):
            variant=design.hypothetical(reason='Unsupported filter shape experiment',changes={parameter:value})
            with self.assertRaises(ValueError):
                lifecycle_filter_settings(variant)

    def test_direction_and_turnaround_controls_follow_filter_variant(self):
        from selected_lifecycle import selected_direction_control_audit,selected_turnaround_requirement
        design=load_design().hypothetical(reason='Control-path filter allocation',changes={
            'blocks.rxfilter_q.parameters.cutoff_hz':[100000.,8e6],
            'blocks.txfilter_i.parameters.cutoff_hz':[100000.,10e6]})
        direction=selected_direction_control_audit(design.contract,design=design)
        self.assertEqual(direction['selected_controls']['rx_cutoff_hz'],8e6)
        self.assertEqual(direction['selected_controls']['tx_cutoff_hz'],10e6)
        budget=selected_turnaround_requirement(design.contract,design=design)
        self.assertEqual(budget['filter_configuration'],{'rx_cutoff_hz':8e6,'tx_cutoff_hz':10e6})

        import json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        import baseline_envelope as b
        import selected_lifecycle as lifecycle
        hashes=b.baseline_source_hashes()
        self.assertIn('system_model/architecture_fast/design_definition.py',hashes)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'evidence').mkdir()
            path=root/'evidence/selected-lifecycle.json';path.write_text('{}')
            with patch.object(b,'P',root),patch.object(lifecycle,'load_design',return_value=design), \
                 patch('sys.argv',['selected_lifecycle.py','--turnaround-requirement']), \
                 patch.object(b,'baseline_source_hashes',side_effect=[hashes,hashes]):
                lifecycle.main()
            saved=path.read_text()
            self.assertEqual(json.loads(saved)['selected_turnaround_requirement']['sources_sha256'],hashes)
            changed=dict(hashes);changed['system_model/architecture_fast/design_definition.py']='changed'
            with patch.object(b,'P',root),patch.object(lifecycle,'load_design',return_value=design), \
                 patch('sys.argv',['selected_lifecycle.py','--turnaround-requirement']), \
                 patch.object(b,'baseline_source_hashes',side_effect=[hashes,changed]):
                with self.assertRaisesRegex(RuntimeError,'Sources changed'):
                    lifecycle.main()
            self.assertEqual(path.read_text(),saved)

    def test_lifecycle_replay_defaults_follow_paired_filter_inventory(self):
        from selected_lifecycle import extended_sar_transport,lifecycle_filter_settings
        design=load_design().hypothetical(reason='Replay filter allocation variant',changes={
            'blocks.rxfilter_q.parameters.cutoff_hz':[100000.,8e6],
            'blocks.txfilter_i.parameters.cutoff_hz':[100000.,10e6]})
        # An unconverged capture exercises admission metadata, not payload success.
        configs=[design.configure(engine='rf',direction='rx',reference_hz=f,
            sample_divider=64,pga_gain_db=39).record() for f in (2.4e9,2.484e9)]
        capture=dict(design_provenance=design.provenance(),numerical_feedback_converged=False,
            resolved_configurations=configs)
        result=extended_sar_transport(design.contract,capture,design=design)
        self.assertEqual(result['filter_configuration'],{'rx_cutoff_hz':8e6,'tx_cutoff_hz':10e6})
        self.assertEqual(result['verdict'],'rejected_unconverged_analog_feedback')
        self.assertEqual(result['resolved_configuration'],configs[1])
        malformed=dict(capture,resolved_configurations=None)
        with self.assertRaisesRegex(ValueError,'nonempty endpoint configurations'):
            extended_sar_transport(design.contract,malformed,design=design)
        with self.assertRaisesRegex(ValueError,'outside shared paired'):
            extended_sar_transport(design.contract,capture,design=design,tx_cutoff=18e6)
        self.assertEqual(lifecycle_filter_settings(design,1e6,3e6),
                         {'rx_cutoff_hz':1e6,'tx_cutoff_hz':3e6})

    def test_packet_filters_reject_settings_outside_paired_inventory(self):
        from baseline_envelope import configured_environment
        from ble_packet import joined_scan_request,transmitted_scan_response
        design=load_design()
        rx=configured_environment(design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=39))
        with self.assertRaisesRegex(ValueError,'outside shared paired rx'):
            joined_scan_request(rx,design.contract,rx_cutoff_hz=10e6)
        tx_config=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64)
        tx=configured_environment(tx_config)
        request={'response':{'reply_armed':True},'settings':{'sample_hz':tx_config.sample_hz,'tx_cutoff_hz':20e6}}
        with self.assertRaisesRegex(ValueError,'outside shared paired tx'):
            transmitted_scan_response(request,tx,design.contract)

    def test_waveform_filters_use_shared_paired_range(self):
        from unittest.mock import patch
        from baseline_envelope import configured_environment
        import selected_rf
        design=load_design()
        for direction,simulate,nominal in (('rx',selected_rf.wideband_receive,9.53125e6),
                                            ('tx',selected_rf.wideband_transmit,12e6)):
            variant=design.hypothetical(reason='Narrower Q-lane filter allocation',changes={
                f'blocks.{direction}filter_q.parameters.cutoff_hz':[100000.,nominal*.9]})
            settings=dict(engine='rf',direction=direction,reference_hz=2.4e9,sample_divider=64,
                **({'pga_gain_db':39} if direction=='rx' else {}))
            environment=configured_environment(variant.configure(**settings))
            result=simulate(environment,oversample=128)
            self.assertEqual(result['cutoff_hz'],nominal*.9)
            self.assertEqual(result['design_provenance'],variant.provenance())
            with patch.object(selected_rf,'he_source') as waveform:
                with self.assertRaisesRegex(ValueError,'outside shared paired'):
                    simulate(environment,cutoff_hz=nominal)
                waveform.assert_not_called()
            del environment['filter_parameters']
            with self.assertRaises(KeyError):simulate(environment)

    def test_missing_or_malformed_filter_inventory_fails_at_snapshot_creation(self):
        design=load_design()
        for value in (None,[],[0,1e6],[2e6,1e6],[True,1e6]):
            architecture=design.architecture
            params=architecture['blocks']['rxfilter_i']['parameters']
            if value is None:del params['cutoff_hz']
            else:params['cutoff_hz']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)


    def test_variant_reaches_filter_cutoff_temperature_and_owner_accounting(self):
        from unittest.mock import patch
        from selected_revision_check import filter_budget_screen
        design=load_design().hypothetical(reason='Filter budget operating variant',changes={
            'blocks.rxfilter_q.parameters.cutoff_hz':[100000.,9e6],
            'blocks.board.parameters.nominal_temperature_c':30.})
        with patch('design_definition.load_design',side_effect=AssertionError('unexpected reload')):
            result=filter_budget_screen(design.contract,design=design)
        self.assertEqual(result['cutoff_hz'],9e6)
        self.assertEqual(result['operating_conditions']['temperature_k'],303.15)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['owner_reconciliation']['design_provenance'],design.provenance())
        self.assertEqual(len(result['cases']),12)
        changed=design.hypothetical(reason='Unsupported filter topology',changes={
            'blocks.rxfilter_i.parameters.order':3})
        with self.assertRaisesRegex(ValueError,'fifth-order'):
            filter_budget_screen(changed.contract,design=changed)


class SharedPadEntrySnapshotTests(unittest.TestCase):
    def test_usb_trim_uses_shared_local_values_and_checks_packet_identity(self):
        from selected_revision_check import usb_trim_envelope
        design=load_design().hypothetical(reason='USB trim allocation check',changes={
            'blocks.usbhs.parameters.drive_current_a':.020,
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.})
        packet=dict(conservative_rail_interval_v=[3.3,3.3],sources_sha256={},design_provenance=design.provenance())
        result=usb_trim_envelope(packet,design.architecture)
        self.assertEqual(result['local_termination_interval_ohm'],[57.,63.])
        self.assertEqual(result['remote_termination_interval_ohm'],[42.75,47.25])
        self.assertEqual(result['input_packet_context']['design_provenance'],design.provenance())
        result['input_packet_context']['design_provenance']['documents'].clear()
        result['input_sources_sha256']['injected']='not a source'
        result['rail_interval_v'][0]=0.
        self.assertEqual(packet['design_provenance'],design.provenance())
        self.assertEqual(packet['sources_sha256'],{})
        self.assertEqual(packet['conservative_rail_interval_v'],[3.3,3.3])

        row=next(x for x in result['cases'] if x['output_resistance_ohm']==1000. and x['supply_fraction_per_v']==0.)
        for voltage,local,peer in zip(row['best']['voltage_interval_v'],[57.,63.],[42.75,47.25]):
            supplied=.020*row['best']['trim']+(.4-voltage)/1000.
            drained=voltage/local+voltage/peer+voltage/1e9+voltage/(1e9+2000.)
            self.assertAlmostEqual(supplied,drained,places=13)
        with self.assertRaisesRegex(ValueError,'provenance conflict'):
            usb_trim_envelope(packet,load_design().architecture)

        # The command-level consumer additionally requires current evidence;
        # direct mathematical fixtures above remain intentionally independent.
        from selected_revision_check import validate_saved_design_input,rf_output_load_screen
        import baseline_envelope as b
        from copy import deepcopy
        config=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64)
        saved=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
            sources_sha256=b.baseline_source_hashes())
        self.assertEqual(validate_saved_design_input(saved,design,engine='rf',direction='tx').record(),config.record())
        for corruption in ('identity','configuration','missing_source','changed_source'):
            broken=deepcopy(saved)
            if corruption=='identity':broken.pop('design_provenance')
            elif corruption=='configuration':broken['resolved_configuration']['sample_hz']=1.
            elif corruption=='missing_source':broken['sources_sha256'].pop('verification/stream_codec.py')
            else:broken['sources_sha256']['verification/stream_codec.py']='changed'
            with self.subTest(corruption=corruption),self.assertRaises(ValueError):
                validate_saved_design_input(broken,design,engine='rf',direction='tx')
        with self.assertRaises(ValueError):
            validate_saved_design_input(saved,design,engine='rf',direction='rx')
        # Synthetic RF observations test context retention, not TX performance.
        saved.update(carrier_hz=2.426e9,transmitter=dict(nominal_gain=4.5,
            loaded_average_active_power_w=.001,input_rms_codes=250.,
            electrical=dict(peak_open_v=.5,allowed_open_peak_v=1.)))
        output=rf_output_load_screen(design.architecture,saved)
        self.assertEqual(output['input_baseline_context']['design_provenance'],design.provenance())
        output['input_baseline_context']['design_provenance']['documents'].clear()
        output['baseline_sources_sha256'].clear()
        self.assertEqual(saved['design_provenance'],design.provenance())
        self.assertTrue(saved['sources_sha256'])
        with self.assertRaisesRegex(ValueError,'provenance conflict'):
            rf_output_load_screen(load_design().architecture,saved)

    def test_usb_campaign_centers_termination_probes_on_shared_value(self):
        import baseline_envelope as b
        design=load_design().hypothetical(reason='USB termination campaign propagation',changes={
            'blocks.board.parameters.analog_supply_v':3.267,
            'blocks.board.parameters.digital_supply_v':3.267,
            'blocks.usbhs.parameters.drive_current_a':.020,
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.})
        report=b.usb_hs_level_campaign(design.contract,design=design)
        self.assertTrue(report['cases'])
        for row in report['cases']:
            expected=[57.,63.] if row['fixture']=='asymmetric_termination_and_bonds' else [60.,60.]
            for state in row['states']:
                self.assertEqual(state['local_termination_ohm'],expected)
                self.assertEqual(state['assigned_drive_current_a'],.020)
                self.assertEqual(state['design_provenance'],design.provenance())
        self.assertTrue(report['host_rate_controls'])
        for row in report['host_rate_controls']:
            self.assertEqual(row['diagnostic_intervention']['host_word_hz'],row['word_hz'])
            self.assertEqual(row['ledger']['source_v'],3.267)
            ledger=row['ledger']
            self.assertAlmostEqual(ledger['source_power_w'],3.267*ledger['total_chip_supply_current_a'],places=14)
            self.assertAlmostEqual(ledger['source_power_w'],ledger['delivered_electrical_power_w']+ledger['resistive_loss_w'],places=14)

    def test_static_usb_output_uses_shared_current_and_termination(self):
        import baseline_envelope as b
        design=load_design().hypothetical(reason='Static USB parameter propagation',changes={
            'blocks.usbhs.parameters.drive_current_a':.020,
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.})
        environment,_=b.usb_supply_environment(design)
        ledger=b.partitioned_dc_ledger(environment,dict(link_r_ohm=1e-5))
        result=b.usb_hs_output(environment,ledger,drive_node=0,bond_r_ohm=.2)
        expected=45.*(.020*60.+result['loaded_dc_ground_v'])/(60.+45.+.2)
        self.assertAlmostEqual(result['board_dc_v'][0],expected,places=12)
        self.assertEqual(result['local_termination_ohm'],[60.,60.])
        self.assertEqual(result['drive_current_a'],.020)
        self.assertFalse(result['termination_override'])
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration'],environment['resolved_configuration'])
        self.assertEqual(result['dc_ledger'],ledger)
        self.assertEqual(result['diagnostic_assumptions']['current_source'],'ideal_constant_current')
        result['design_provenance']['documents'].clear()
        result['dc_ledger']['owner_current_a'].clear()
        self.assertEqual(environment['design_provenance'],design.provenance())
        self.assertTrue(ledger['owner_current_a'])

        missing=dict(environment);del missing['wired_usb_parameters']
        with self.assertRaises(KeyError):b.usb_hs_output(missing,ledger,drive_node=0)

    def test_actual_mode_sequence_uses_shared_usb_drive_and_termination(self):
        from selected_revision_check import shared_pad_envelope
        design=load_design().hypothetical(reason='USB mode-sequence propagation',changes={
            'blocks.usbhs.parameters.drive_current_a':.020,
            'blocks.usbhs.parameters.termination_ohm_per_leg':60.})
        result=shared_pad_envelope(3.3,design=design)
        stage=next(row for row in result['stages'] if row['name']=='usb_current_drive')
        expected=.020/(1/60.+1/45.+1/1e9+1/(1e9+2000.))
        self.assertAlmostEqual(stage['pad_v'][0],expected,places=10)
        self.assertEqual(stage['local_drive']['current_a'],.020)
        self.assertEqual(stage['local_hs_termination_ohm'],60.)
        self.assertEqual(result['design_provenance'],design.provenance())

    def test_loader_rejects_incomplete_or_invalid_pad_before_factory(self):
        design=load_design()
        paths=[('blocks',block,'parameters',key) for block,keys in (
            ('usbhs',('drive_current_a','termination_ohm_per_leg','squelch_v')),
            ('usbfs',('pullup_ohm','pulldown_ohm','effective_output_r_ohm')))
            for key in keys]
        paths.extend(('pad_behavioral_contract','shared_wired_network',key) for key in (
            'base_shunt_cap_f_per_leg','inactive_branch_cap_f_per_leg','mutual_cap_f',
            'divider_cap_f_per_leg','divider_top_ohm','divider_bottom_ohm',
            'divider_off_ohm','serial_differential_termination_ohm'))
        for path in paths:
            for invalid in ('missing',True,0.,-1.):
                with self.subTest(path=path,invalid=invalid):
                    architecture=design.architecture;parent=architecture
                    for part in path[:-1]:parent=parent[part]
                    if invalid=='missing':del parent[path[-1]]
                    else:parent[path[-1]]=invalid
                    with self.assertRaises(ValueError):
                        DesignDefinition.from_documents(design.contract,architecture)
        architecture=design.architecture
        architecture['blocks']['wirepad']['parameters']['capacitance_f_per_leg']*=2
        with self.assertRaisesRegex(ValueError,'odd-mode capacitance'):
            DesignDefinition.from_documents(design.contract,architecture)

    def test_pad_rejects_foreign_supply_and_architecture_before_simulation(self):
        from selected_revision_check import shared_pad_envelope
        design=load_design()
        foreign=design.hypothetical(reason='Foreign pad snapshot',changes={
            'blocks.board.parameters.nominal_temperature_c':30.})
        with self.assertRaisesRegex(ValueError,'Pad architecture conflicts'):
            shared_pad_envelope(3.3,architecture=foreign.architecture,design=design)
        for supply in ({},{'design_provenance':foreign.provenance()}):
            with self.assertRaisesRegex(ValueError,'USB supply conflicts'):
                shared_pad_envelope(3.3,architecture=design.architecture,design=design,usb_supply=supply)


    def test_pad_entry_preserves_package_variant_and_both_owner_configs(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design().hypothetical(reason='Shared-pad package propagation',changes={
            'blocks.power.parameters.shared_return_l_h':.35e-9,
            'blocks.power.parameters.reduced_pdn_model.network.die_esl':.3e-9})
        seen=[]
        original=screen.b.reference_payload_environment
        def clock(environment,*args,**kwargs):
            seen.append(environment)
            return original(environment,*args,**kwargs)
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(screen,'shared_pad_envelope',return_value={}) as pad:
            result=screen.shared_pad_design_screen(design)
        self.assertEqual(seen[0]['network']['return_l_h'],.35e-9)
        self.assertEqual(seen[0]['network']['network']['die_esl'],.3e-9)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['direction'],'duplex')
        self.assertEqual(result['usb_resolved_configuration']['inventory_mode'],'usb')
        self.assertEqual(pad.call_args.kwargs['usb_supply']['design_provenance'],design.provenance())
        self.assertEqual(pad.call_args.kwargs['architecture'],design.architecture)

    def test_rejected_clock_does_not_promote_pad_evidence(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{'status':'injected_rejection'})), \
             patch.object(screen,'shared_pad_envelope',side_effect=AssertionError('pad must not run')):
            result=screen.shared_pad_design_screen(design)
        self.assertEqual(result['status'],'rejected_wired_clock')
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertIsNone(result['pad'])


class CommonEnvelopeSnapshotTests(unittest.TestCase):
    def test_common_envelope_keeps_variant_and_package_context(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import converter_dynamics
        design=load_design().hypothetical(reason='Common wired inventory propagation',changes={
            'blocks.ctle.parameters.zero_s':400e-12,
            'blocks.ctle.parameters.dc_gain':.8,
            'blocks.cdr.parameters.detector_jitter_rms_s':3e-12,
            'blocks.cdr.parameters.holdover_bits':96})
        seen=[]
        def clock(environment,*args,**kwargs):
            return environment,dict(ledger=environment['ledger'],status='fixture_accepted')
        def tone(environment,parameters,**kwargs):
            self.assertEqual(environment['converter_parameters']['reference_r_ohm'],parameters.reference_r_ohm)
            seen.append(environment['design_provenance']['design_fingerprint'])
            return {'construction_fixture':True}
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(converter_dynamics,'tone_precision',side_effect=tone), \
             patch.object(screen,'shared_pad_envelope',return_value={}), \
             patch.object(screen.b,'causal_receiver_envelope',return_value={}) as receiver:
            report=screen.common_envelope_screen(design.contract,design.architecture,design=design)
        self.assertEqual(report['design_provenance'],design.provenance())
        self.assertEqual(len(report['cases']),6)
        self.assertGreater(len(set(seen)),1)
        for call in receiver.call_args_list:
            impairment=call.kwargs['timing_scenarios'][0]
            self.assertEqual(impairment['ctle_zero_s'],400e-12)
            self.assertEqual(impairment['detector_noise_rms_s'],3e-12)
            self.assertAlmostEqual(impairment['signal_scale'],.8*impairment['rail_dc_v']/3.3)
        for row in report['cases']:
            self.assertEqual(row['resolved_configuration']['engine'],row['mode'])
            if row['package']==screen.b.BASELINE_PACKAGE_CASE:
                self.assertEqual(row['scenario_overrides'],[])
            else:self.assertEqual(len(row['scenario_overrides']),2)
            if row['mode']=='wire':
                cases=row['payload']['cdr_cases']
                self.assertEqual(cases[0]['holdover_ui'],96)
                self.assertFalse(cases[0]['holdover_override'])
                self.assertEqual(cases[2]['holdover_ui'],512)
                self.assertTrue(cases[2]['holdover_override'])
                for case in cases:
                    self.assertEqual(case['holdover_override'],case['holdover_ui']!=96)
            if row['mode']=='rf':
                for converter in row['payload']['converter_cases']:
                    if converter['name']=='combined_loading_stress':
                        self.assertTrue(converter['design_provenance']['circuit_experiments'])


class RFChainSnapshotTests(unittest.TestCase):
    def test_solver_rejection_preserves_resolved_adverse_context(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design();context={}
        with patch.object(screen.b,'reference_payload_environment',side_effect=ValueError('Injected clock-model rejection')):
            with self.assertRaisesRegex(ValueError,'Injected clock-model rejection'):
                screen.rf_chain_case(design.contract,design.architecture,'wideband_adverse',
                                     design=design,rejection_context=context)
        self.assertEqual(context['name'],'wideband_adverse')
        self.assertEqual(context['resolved_configuration']['direction'],'rx')
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertTrue(context['design_provenance']['circuit_experiments'])
        self.assertEqual(context['scenario_overrides'],[])
        self.assertEqual(context['wanted_dbm'],-65.)
        self.assertEqual(context['design_binding']['inventory_mode'],'rf_rx')
        self.assertNotIn('accepted',context)
        import contextlib,io
        with patch('sys.argv',['selected_revision_check.py','--rf-chain-case','wideband_adverse']), \
             patch.object(screen.b,'reference_payload_environment',side_effect=ValueError('Injected clock-model rejection')), \
             patch.object(screen.b,'write_evidence') as save,contextlib.redirect_stdout(io.StringIO()):
            screen.main()
        report=save.call_args.args[1]['rf_chain_first_version']['cases']['wideband_adverse']
        self.assertEqual(report['status'],'model_rejected')
        self.assertFalse(report['accepted'])
        self.assertEqual(report['design_provenance'],context['design_provenance'])
        self.assertEqual(report['resolved_configuration'],context['resolved_configuration'])
        self.assertEqual(report['scenario_stimuli'],context['scenario_stimuli'])
        self.assertEqual(report['sources_sha256'],screen.b.baseline_source_hashes())
        # Source drift must preserve earlier evidence, including rejected runs.
        original_hashes=screen.b.baseline_source_hashes()
        changed_hashes=dict(original_hashes)
        changed_hashes['verification/stream_codec.py']='changed'
        with patch('sys.argv',['selected_revision_check.py','--rf-chain-case','wideband_adverse']), \
             patch.object(screen.b,'reference_payload_environment',side_effect=ValueError('Injected clock-model rejection')), \
             patch.object(screen.b,'baseline_source_hashes',side_effect=[original_hashes,changed_hashes]), \
             patch.object(screen.b,'write_evidence') as save:
            with self.assertRaisesRegex(RuntimeError,'Sources changed during selected review'):
                screen.main()
            save.assert_not_called()
        with patch.object(DesignDefinition,'configure',side_effect=ValueError('Injected setting rejection')):
            with self.assertRaisesRegex(ValueError,'Injected setting rejection'):
                screen.rf_chain_case(design.contract,design.architecture,'wideband_adverse',
                                     design=design,rejection_context=context)
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertIsNone(context['resolved_configuration'])
        self.assertEqual(context['requested_configuration']['direction'],'rx')
        self.assertEqual(context['configuration_resolution'],'not_completed')

    def test_rf_chain_cases_keep_rejected_clock_provenance(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})):
            nominal=screen.rf_chain_case(design.contract,design.architecture,'wideband_gain36',design=design)
            adverse=screen.rf_chain_case(design.contract,design.architecture,'wideband_adverse',design=design)
            tx=screen.rf_chain_case(design.contract,design.architecture,'tx_nominal',design=design)
        self.assertEqual(nominal['design_provenance'],design.provenance())
        self.assertEqual(nominal['resolved_configuration']['pga_gain_db'],36.)
        self.assertNotEqual(adverse['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertTrue(adverse['design_provenance']['circuit_experiments'])
        self.assertEqual(tx['resolved_configuration']['direction'],'tx')
        self.assertEqual(adverse['status'],'clock_rejected')

    def test_adverse_receiver_arguments_match_variant_not_unrecorded_overrides(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        import wideband_packet
        design=load_design();seen={}
        def clock(environment,*args,**kwargs):
            seen['environment']=environment
            return dict(environment,delivered_phase_tones=()),{}
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(wideband_packet,'run_acquisition_case',side_effect=RuntimeError('receiver boundary')) as receiver:
            with self.assertRaisesRegex(RuntimeError,'receiver boundary'):
                screen.rf_chain_case(design.contract,design.architecture,'wideband_adverse',design=design)
        parameters=seen['environment']['receiver_parameters']['lna']
        self.assertEqual(receiver.call_args.kwargs['noise_figure_db'],parameters['noise_figure_db'])
        self.assertEqual(receiver.call_args.kwargs['input_iip3_dbm'],parameters['iip3_dbm'])
        self.assertEqual(receiver.call_args.kwargs['comparator_model']['tau_s'],100e-12)
        self.assertEqual(parameters['noise_figure_db'],design.architecture['blocks']['lna']['parameters']['noise_figure_db']+2.)
        self.assertNotIn('gain_tau_s',receiver.call_args.kwargs)
        from selected_rf import receiver_pga_response,wideband_receive
        self.assertEqual(receiver_pga_response(seen['environment']),2e-6)
        for lane in ('i','q'):
            changes=seen['environment']['design_provenance']['circuit_experiments'][-1]['changes']
            self.assertIn(dict(path=f'blocks.pga_{lane}.parameters.gain_response_tau_s',
                before=design.architecture['blocks']['pga_'+lane]['parameters']['gain_response_tau_s'],
                after=2e-6),changes)
        # Exercise the real receiver guard, stopping only at waveform generation.
        with patch('selected_rf.he_source',side_effect=RuntimeError('waveform boundary')):
            with self.assertRaisesRegex(RuntimeError,'waveform boundary'):
                wideband_receive(seen['environment'],gain_initial_db=30.,gain_command_s=2e-6,
                    noise_figure_db=parameters['noise_figure_db'],
                    input_iip3_dbm=parameters['iip3_dbm'])



    def test_narrowband_campaign_reaches_shared_receiver_without_option_conflicts(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        def clock(environment,*args):
            return dict(environment,delivered_phase_tones=()),dict(ledger=environment['ledger'])
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch('selected_rf.minimum_envelope_oversample',return_value=256), \
             patch.object(screen.b,'joined_scan_request',side_effect=RuntimeError('waveform boundary')) as receiver:
            with self.assertRaisesRegex(RuntimeError,'waveform boundary'):
                screen.rf_chain_case(design.contract,design.architecture,'narrowband_nominal',design=design)
        environment=receiver.call_args.args[0]
        self.assertEqual(environment['design_provenance'],design.provenance())
        self.assertEqual(receiver.call_args.kwargs['initial_gain_db'],environment['resolved_configuration']['pga_gain_db'])
        self.assertEqual(receiver.call_args.kwargs['gain_codes_db'],
            tuple(design.architecture['blocks']['pga_i']['parameters']['gain_db']))

    def test_narrowband_reply_uses_separate_tx_configuration_and_budget(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design()
        # Explicit success fixture reaches TX routing; it is not packet evidence.
        rx=dict(correct_request=True,converter=dict(evaluated_supply_interval_v=[3.,3.3],
            reference_with_bias_peak_a=.001,reference_interval_v=[1.,1.]),
            gain_control={'pga_clipped_samples':0},
            frontend_nonlinearity={'within_assigned_small_compression_range':True},
            reference_feedback={'numerical_feedback_converged':True},pga_nominal_peak_limit_v=.8)
        for reject_tx in (False,True):
            with self.subTest(reject_tx=reject_tx):
                directions=[]
                def clock(environment,*args):
                    direction=environment['resolved_configuration']['direction']
                    directions.append(direction)
                    return (None if reject_tx and direction=='tx' else dict(environment,delivered_phase_tones=()),
                            dict(ledger=environment['ledger']))
                def transmit(request,environment,contract,**options):
                    self.assertEqual(environment['resolved_configuration']['direction'],'tx')
                    self.assertEqual(environment['design_provenance'],design.provenance())
                    self.assertEqual(options['rf_bias_a'],environment['ledger']['owner_current_a']['rf'])
                    return dict(transmitted=False)
                with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
                     patch('selected_rf.minimum_envelope_oversample',return_value=256), \
                     patch.object(screen.b,'coupled_scan_request',return_value=(rx,{})), \
                     patch.object(screen.b,'transmitted_scan_response',side_effect=transmit) as reply:
                    row=screen.rf_chain_case(design.contract,design.architecture,'narrowband_nominal',design=design)
                self.assertEqual(directions,['rx','tx'])
                self.assertEqual(reply.call_count,0 if reject_tx else 1)
                self.assertEqual(row['tx_resolved_configuration']['direction'],'tx')
                self.assertFalse(row['exchange_accepted'])


class FilterProbeSnapshotTests(unittest.TestCase):
    def test_filter_probes_retain_snapshot_and_declared_assumptions(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design().hypothetical(reason='Filter probe package fixture',changes={
            'blocks.power.parameters.shared_return_l_h':.45e-9})
        with patch.object(screen.b,'reference_payload_environment',return_value=(None,{})), \
             patch.object(screen,'load_design',side_effect=AssertionError('Unexpected reload')):
            memory=screen.rx_memory_screen(design.contract,design=design)
            realization=screen.filter_realization_screen(design.contract,design=design)
        for result in (memory,realization):
            self.assertEqual(result['design_provenance'],design.provenance())
            self.assertEqual(result['resolved_configuration']['direction'],'rx')
            self.assertEqual(result['probe_assumptions']['supply_delay_sign'],-1.)
            self.assertIn('adc_switching',result['probe_assumptions'])
        self.assertEqual(memory['verdict'],'clock_rejected')
        self.assertEqual(realization['coupled_receiver_cases'],[])
        self.assertEqual(realization['paired_rx_filter_budget_a'],sum(
            design.architecture['blocks'][name]['resource_allocation']['current_budget_ma']['rf_rx']
            for name in ('rxfilter_i','rxfilter_q'))/1000)

    def test_memory_frontend_arguments_come_from_snapshot(self):
        from unittest.mock import patch
        import selected_revision_check as screen
        design=load_design().hypothetical(reason='Filter frontend fixture',changes={
            'blocks.lna.parameters.noise_figure_db':8.,'blocks.lna.parameters.iip3_dbm':-2.})
        def clock(environment,*args,**kwargs):return environment,{}
        with patch.object(screen.b,'reference_payload_environment',side_effect=clock), \
             patch.object(screen.b,'coupled_scan_request',side_effect=RuntimeError('receiver boundary')) as receiver:
            with self.assertRaisesRegex(RuntimeError,'receiver boundary'):
                screen.rx_memory_screen(design.contract,design=design)
        options=receiver.call_args.kwargs['rx_options']
        self.assertEqual(options['noise_figure_db'],8.)
        self.assertEqual(options['input_iip3_dbm'],-2.)


class CurrentProbeSnapshotTests(unittest.TestCase):
    def test_current_probe_uses_supplied_package_and_tx_inventory(self):
        from selected_revision_check import tx_current_environment
        design=load_design().hypothetical(reason='Current-probe package fixture',changes={
            'blocks.power.parameters.shared_return_l_h':.7e-9})
        environment,context=tx_current_environment(design.contract,design=design)
        self.assertEqual(context['design_provenance'],design.provenance())
        self.assertEqual(environment['network']['return_l_h'],.7e-9)
        self.assertEqual(environment['resolved_configuration']['inventory_mode'],'rf_tx')
        self.assertEqual(context['result_role'],'numerical_component_diagnostic')
        self.assertEqual(context['probe_assumptions']['supply_sign'],-1.)

    def test_serialized_current_continuation_matches_uninterrupted_trace(self):
        from selected_revision_check import native_current_continuation
        design=load_design()
        result=native_current_continuation(design.contract,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['direction'],'tx')
        self.assertLess(max(result['continuation_peak_errors'].values()),1e-10)
        self.assertGreater(result['reset_peak_errors']['rail_v'],1e-6)


class TurnaroundSnapshotTests(unittest.TestCase):
    def test_completion_bound_has_one_owner_and_changes_budget_directly(self):
        from selected_lifecycle import selected_turnaround_requirement
        design=load_design()
        original=selected_turnaround_requirement(design.contract,design=design)
        contract=design.contract
        contract['physical_services']['sar_timing']['maximum_conversion_s']+=1e-9
        variant=DesignDefinition.from_documents(contract,design.architecture)
        changed=selected_turnaround_requirement(variant.contract,design=variant)
        self.assertAlmostEqual(changed['assigned_overhead_s']-original['assigned_overhead_s'],1e-9,places=15)
        self.assertEqual(changed['design_provenance'],variant.provenance())
        self.assertEqual(changed['resolved_configurations']['rx']['direction'],'rx')
        self.assertEqual(changed['resolved_configurations']['tx']['direction'],'tx')
        del contract['physical_services']['sar_timing']['maximum_conversion_s']
        with self.assertRaisesRegex(ValueError,'Missing required design parameter'):
            DesignDefinition.from_documents(contract,design.architecture)


class DirectionControlSnapshotTests(unittest.TestCase):
    def test_direction_control_uses_shared_startup_and_settings(self):
        from selected_lifecycle import selected_direction_control_audit
        original=load_design();contract=original.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=25e-6
        design=DesignDefinition.from_documents(contract,original.architecture)
        result=selected_direction_control_audit(design.contract,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertAlmostEqual(result['fallback_startup_wait_s'],25e-6,places=15)
        self.assertEqual(result['resolved_configurations']['rx']['direction'],'rx')
        self.assertEqual(result['resolved_configurations']['tx']['direction'],'tx')
        self.assertGreater(result['generic_gate']['verified_tx_bits'],0)
        self.assertEqual(result['retained_clock_direction_operation_demonstrated'],'control_path_only')

    def test_unsupported_sample_format_is_not_silently_used(self):
        from selected_lifecycle import selected_direction_control_audit
        design=load_design().hypothetical(reason='Direction adapter width fixture',changes={
            'blocks.adc_i.parameters.transport_bits':14})
        with self.assertRaisesRegex(ValueError,'paired 12-bit samples'):
            selected_direction_control_audit(design.contract,design=design)


class TransportAssumptionSnapshotTests(unittest.TestCase):
    def test_wired_service_campaign_preserves_shared_startup_and_provenance(self):
        from unittest import mock
        from selected_lifecycle import wired_snapshot_service_check
        baseline=load_design();contract=baseline.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        design=DesignDefinition.from_documents(contract,baseline.architecture)
        with mock.patch('design_definition.load_design',side_effect=AssertionError('unexpected reload')):
            result=wired_snapshot_service_check(contract,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['direction'],'rx')
        self.assertEqual(result['startup_guard_s'],30e-6)
        self.assertEqual(result['queue_depth_bits'],contract['transport']['scheduling']['ingress_bits_per_source'])
        self.assertEqual(result['missed_service_control']['flow']['fault'],'overflow')


    def test_lifecycle_factory_consumes_startup_without_reloading_or_defaults(self):
        import baseline_envelope as envelope
        from selected_lifecycle import selected_transport_assumptions
        baseline=load_design();contract=baseline.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        design=DesignDefinition.from_documents(contract,baseline.architecture)
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
                                sample_divider=64,pga_gain_db=39.)
        environment=envelope.configured_environment(config)
        assumptions=selected_transport_assumptions(environment)
        self.assertEqual(assumptions.startup_s,30e-6)
        self.assertEqual(assumptions.d2h_clock_scale*312.5e6,config.host_word_hz)
        del environment['transport_parameters']
        with self.assertRaisesRegex(ValueError,'missing startup'):
            selected_transport_assumptions(environment)

    def test_independent_transport_fixture_can_retain_primitive_assumptions(self):
        from selected_lifecycle import selected_transport_assumptions
        primitive={'host_spectrum':{'h2d_word_hz':100e6,'d2h_word_hz':80e6}}
        assumptions=selected_transport_assumptions(primitive)
        self.assertAlmostEqual(assumptions.h2d_clock_scale*312.5e6,100e6)
        self.assertAlmostEqual(assumptions.d2h_clock_scale*312.5e6,80e6)


class HostFollowTransportSnapshotTests(unittest.TestCase):
    def test_transport_rejects_foreign_configuration_and_stripped_inventory_identity(self):
        import copy
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        design=load_design()
        config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
        environment=configured_environment(config)
        other=design.hypothetical(reason='Identical rates, different receiver hardware',changes={
            'blocks.ctle.parameters.dc_gain':2.})
        foreign=copy.deepcopy(environment)
        foreign['resolved_configuration']=other.configure(engine='wire',direction='duplex',
            reference_hz=2.5e9,host_divider=8).record()
        with self.assertRaisesRegex(ValueError,'environment design provenance'):
            selected_transport_assumptions(foreign)
        for invalid in ({},None,'unbound'):
            broken=copy.deepcopy(environment);broken['resolved_configuration']=invalid
            with self.assertRaisesRegex(ValueError,'requires resolved configuration'):
                selected_transport_assumptions(broken)
        missing=copy.deepcopy(environment);del missing['resolved_configuration']
        with self.assertRaisesRegex(ValueError,'requires resolved configuration'):
            selected_transport_assumptions(missing)
        for invalid in ({},None,'unbound'):
            broken=copy.deepcopy(environment);broken['design_provenance']=invalid
            with self.assertRaisesRegex(ValueError,'requires design provenance'):
                selected_transport_assumptions(broken)
        for key in ('startup_s','h2d_word_hz','d2h_word_hz'):
            for invalid in (0.,float('nan'),True):
                broken=copy.deepcopy(environment);broken['transport_parameters'][key]=invalid
                with self.assertRaisesRegex(ValueError,'shared transport parameter'):
                    selected_transport_assumptions(broken)
        del environment['design_provenance']
        with self.assertRaisesRegex(ValueError,'requires design provenance'):
            selected_transport_assumptions(environment)

    def test_host_follow_transport_uses_config_despite_spectrum_surrogate(self):
        import baseline_envelope as envelope
        from selected_lifecycle import selected_transport_assumptions
        original=load_design();contract=original.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        design=DesignDefinition.from_documents(contract,original.architecture)
        config=design.configure(engine='wire',direction='duplex',reference_hz=480e6,
            host_clock_source='host_follow',host_input_hz=100e6,wired_pad_path='bidirectional')
        environment=envelope.configured_environment(config)
        assumptions=selected_transport_assumptions(environment)
        self.assertEqual(assumptions.startup_s,30e-6)
        self.assertEqual(assumptions.h2d_clock_scale*312.5e6,100e6)
        self.assertEqual(assumptions.d2h_clock_scale*312.5e6,100e6)
        environment['transport_parameters']['h2d_word_hz']=120e6
        with self.assertRaisesRegex(ValueError,'conflict'):
            selected_transport_assumptions(environment)
        del environment['transport_parameters']['h2d_word_hz']
        with self.assertRaisesRegex(ValueError,'missing transport parameter'):
            selected_transport_assumptions(environment)


class FeedRFProbeSnapshotTests(unittest.TestCase):
    def test_feed_probe_records_circuit_change_and_current_hypothesis(self):
        from unittest.mock import patch
        import feed_rf_probe as probe
        design=load_design()
        with patch.object(probe,'loaded_probe',return_value=(None,{'status':'load_rejected'})):
            environment,row=probe.feed_environment(design,1.,2.,.0125)
        self.assertIsNone(environment)
        self.assertEqual(row['status'],'load_rejected')
        self.assertNotEqual(row['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertTrue(row['design_provenance']['circuit_experiments'])
        self.assertEqual(row['resolved_configuration']['sample_hz'],37.5e6)
        self.assertEqual(row['scenario_stimuli']['wanted_dbm'],-85.)
        self.assertEqual(row['probe_assumptions']['internal_switching_loads'][0]['mean_a'],.020)

    def test_spectral_campaign_preserves_rejected_cases(self):
        from unittest.mock import patch
        import feed_rf_probe as probe
        with patch.object(probe,'loaded_probe',return_value=(None,{'status':'load_rejected'})), \
             patch.object(probe.b,'write_evidence') as write:
            probe.spectra()
        rows=write.call_args.args[1]['cases']
        self.assertEqual(len(rows),3)
        self.assertTrue(all(row['status']=='load_rejected' for row in rows))
        self.assertTrue(all('design_provenance' in row for row in rows))


class PhaseBoundSnapshotTests(unittest.TestCase):
    def test_adc_phase_bound_harmonics_use_the_shared_sar_schedule(self):
        import numpy as np
        from unittest.mock import patch
        from internal_phase_bound import adc_activity_bounds
        from baseline_envelope import configured_environment,environment_converter_parameters
        from converter_dynamics import adc_switching_sources
        design=load_design().hypothetical(reason='ADC harmonic timing check',changes={
            'model_assumptions.paired_sar.parameters.comparator_s':.65e-9})
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                                sample_divider=64,pga_gain_db=39)
        environment=configured_environment(config)
        expected_parameters=environment_converter_parameters(environment)
        captured=[]
        def observed(**kwargs):
            self.assertEqual(kwargs['parameters'],expected_parameters)
            result=adc_switching_sources(**kwargs)
            rate=kwargs['sample_hz'];tau=kwargs['pulse_tau_s']
            durations=expected_parameters.bit_durations_s
            starts=np.array([sum(durations[:i]) for i in range(len(durations))])
            events=[-expected_parameters.acquisition_s,*starts,
                    *(starts+durations-expected_parameters.comparator_s),sum(durations)]
            current=2*sum(np.exp(-2j*np.pi*rate*t) for t in events)/len(events)/(1+2j*np.pi*rate*tau)**3
            np.testing.assert_allclose(result[rate],[0,-current,0,current,0],rtol=1e-12,atol=1e-14)
            captured.append((rate,tau))
            return result
        clock=dict(input_peak_v=0.,input_slope_v_per_s=0.,carrier_amplitude_v=.3,
                   delay_peak_s=0.,delay_slope=0.,leg_bound_v=np.array([.3,.3]))
        with patch('converter_dynamics.adc_switching_sources',side_effect=observed):
            result=adc_activity_bounds(environment,[3.,3.3],
                design.contract['physical_services']['external_clock_input']['input_model'],clock)
        self.assertEqual(len(captured),6)
        self.assertEqual(len(result['cases']),36)

    def test_phase_source_partition_uses_shared_transition_charge(self):
        import numpy as np
        from internal_phase_bound import phase_host_groups
        from baseline_envelope import configured_environment
        design=load_design();key='model_assumptions.host_switching.parameters.d2h_internal_charge_c'
        environments=[]
        for charge in (0.,14e-12):
            variant=design.hypothetical(reason='Transition-charge partition check',changes={key:charge})
            environments.append(configured_environment(variant.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)))
        groups=[phase_host_groups(e) for e in environments]
        h=environments[0]['host_spectrum'];f=h['d2h_word_hz']
        expected=2*f*6*14e-12/(1+2j*np.pi*f*h['d2h_internal_tau_s'])
        np.testing.assert_allclose(groups[1][0][f]-groups[0][0][f],[-expected,0,expected,0,0],rtol=1e-12,atol=1e-15)
        for frequency in set(groups[0][1])|set(groups[1][1]):
            np.testing.assert_allclose(groups[1][1].get(frequency,np.zeros(5)),
                groups[0][1].get(frequency,np.zeros(5)),rtol=1e-12,atol=1e-15)

    def test_feed_runner_records_shared_manifest_and_rejects_source_drift(self):
        import hashlib,io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import feed_usb_probe as probe
        with patch.object(probe.b,'write_evidence') as save,redirect_stdout(io.StringIO()):
            probe.main()
        report=save.call_args.args[1]
        self.assertEqual(report['design_provenance'],load_design().provenance())
        self.assertEqual(len(report['cases']),4)
        for name,digest in report['sources_sha256'].items():
            self.assertEqual(hashlib.sha256((probe.b.P/name).read_bytes()).hexdigest(),digest)
        for name in ('verification/selected_rf.py','system_model/connected/protocol_pad.py'):
            self.assertIn(name,report['sources_sha256'])
        stale=probe.probe_source_hashes();stale['verification/selected_rf.py']='stale'
        with patch.object(probe,'probe_source_hashes',return_value=stale), \
             patch.object(probe.b,'write_evidence') as save,redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,'Sources changed'):
                probe.main()
            save.assert_not_called()

    def test_phase_bound_uses_changed_supply_delay_law(self):
        import numpy as np
        from internal_phase_bound import phase_environment,tx_current_margin
        base=load_design();contract=base.contract
        contract['physical_services']['external_clock_input'].update(
            supply_sensitivity_ps_per_mv=.07,supply_delay_pole_hz=5e6)
        design=DesignDefinition.from_documents(contract,base.architecture)
        power=design.architecture['blocks']['power']['parameters']
        environment,context,_=phase_environment(design,'rf',2.426e9,
            power['shared_return_l_h'],power['reduced_pdn_model']['network']['die_esl'],
            power['reduced_pdn_model']['network']['package_r'],1.)
        clock=dict(input_peak_v=0.,input_slope_v_per_s=0.,carrier_amplitude_v=1.,
            leg_bound_v=np.array([.1,.1]),delay_slope=0.)
        result=tx_current_margin(environment,[2.501,3.2],
            contract['physical_services']['external_clock_input']['input_model'],clock,frequencies=[1e6])
        row=result['cases'][0]
        expected=row['maximum_sufficient_peak_current_a']*row['rail_transfer_abs_ohm']*.07e-9/(1+(1e6/5e6)**2)**.5
        self.assertGreater(expected,0.)
        self.assertAlmostEqual(row['added_delay_peak_at_limit_s']/expected,1.,places=12)
        self.assertEqual(result['supply_delay_pole_hz'],5e6)
        self.assertEqual(context['probe_assumptions']['supply_delay_ps_per_mv'],.07)

    def test_phase_bound_separates_circuit_package_and_current_inputs(self):
        from internal_phase_bound import phase_environment
        design=load_design()
        environment,context,loads=phase_environment(design,'rf',2.426e9,2e-9,1e-9,1.,2.)
        self.assertEqual(environment['network']['network']['package_r'],1.)
        self.assertEqual(environment['network']['return_l_h'],2e-9)
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(len(context['scenario_overrides']),2)
        self.assertEqual(context['probe_assumptions']['internal_switching_loads'],loads)
        self.assertEqual(context['resolved_configuration']['sample_divider'],64)
        self.assertEqual(design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['package_r'],2.)

    def test_phase_bound_retains_owner_budget_for_adverse_pulses(self):
        from internal_phase_bound import phase_environment
        import baseline_envelope as envelope
        design=load_design()
        environment,context,loads=phase_environment(design,'wire',2.5e9,.25e-9,.2e-9,2.,100.)
        self.assertEqual(context['design_provenance'],design.provenance())
        self.assertEqual(context['resolved_configuration']['host_divider'],8)
        with self.assertRaisesRegex(ValueError,'Internal pulse mean exceeds owner DC budget'):
            envelope.internal_switching_sources(loads,owner_current_a=environment['inventory_current_a'])


class USBFeedSnapshotTests(unittest.TestCase):
    def test_usb_feed_uses_usb_inventory_and_preserves_feed_variant(self):
        from feed_usb_probe import feed_environment
        import baseline_envelope as envelope
        design=load_design()
        baseline,base_context=feed_environment(design,2.)
        variant,context=feed_environment(design,1.)
        self.assertEqual(base_context['design_provenance'],design.provenance())
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(context['resolved_configuration']['reference_hz'],480e6)
        self.assertEqual(context['resolved_configuration']['wired_pad_path'],'bidirectional')
        self.assertEqual(variant['transport_parameters']['h2d_word_hz'],100e6)
        self.assertEqual(variant['transport_parameters']['d2h_word_hz'],100e6)
        self.assertEqual(baseline['network']['network']['package_r'],2.)
        self.assertEqual(variant['network']['network']['package_r'],1.)
        ledger=envelope.partitioned_dc_ledger(variant,dict(link_r_ohm=1e-5))
        self.assertAlmostEqual(ledger['total_chip_supply_current_a'],sum(variant['inventory_current_a'].values()))


class ReferenceCampaignSnapshotTests(unittest.TestCase):
    def test_reference_campaign_resolves_rf_and_wired_ownership(self):
        from reference_input_probe import configured_probe_environment
        design=load_design()
        for mode,carrier,transmit in [('rf',2.426e9,False),('rf',2.426e9,True),('wire',2.5e9,False)]:
            environment,context=configured_probe_environment(design,mode,carrier,transmit=transmit)
            self.assertEqual(context['design_provenance'],design.provenance())
            self.assertEqual(environment['resolved_configuration'],context['resolved_configuration'])
            self.assertEqual(environment['internal_switching_loads'],context['probe_assumptions']['internal_switching_loads'])
            if mode=='rf' and not transmit:self.assertEqual(context['resolved_configuration']['pga_gain_db'],42.)
            if mode=='wire':self.assertEqual(context['resolved_configuration']['host_divider'],8)

    def test_wake_campaign_retains_rejected_clock_context(self):
        from unittest.mock import patch
        import reference_input_probe as probe
        design=load_design()
        with patch.object(probe.b,'single_ended_reference_payload_environment',return_value=(None,{'ledger':{}})), \
             patch.object(probe,'paired_environment',return_value=(None,{'accepted':False})), \
             patch.object(probe,'write_report') as write:
            probe.shared_wake_campaign(2.426e9,'unused',design=design)
        report=write.call_args.args[1]
        self.assertTrue(report['campaign_complete'])
        self.assertEqual(len(report['cases']),6)
        for row in report['cases']:
            self.assertEqual(row['status'],'clock_rejected')
            self.assertEqual(row['design_provenance'],design.provenance())
            self.assertEqual(row['resolved_configuration']['direction'],'tx')


class ReferenceRequirementSnapshotTests(unittest.TestCase):
    def test_hypothetical_gain_cannot_change_baseline(self):
        from reference_input_probe import gain_requirement_environment
        design=load_design()
        environment,context=gain_requirement_environment(design,2.4e9,2e-9,1e-9)
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(context['resolved_configuration']['pga_gain_db'],54.)
        self.assertEqual(environment['network']['return_l_h'],2e-9)
        self.assertEqual(len(context['scenario_overrides']),2)
        self.assertEqual(len(context['design_provenance']['circuit_experiments']),1)
        with self.assertRaises(ValueError):
            design.configure(engine='rf',direction='rx',reference_hz=2.4e9,sample_divider=64,pga_gain_db=54.)

    def test_numerical_package_fixture_retains_shared_circuit_changes(self):
        from reference_input_probe import package_check_environment
        design=load_design().hypothetical(reason='Package solver parameter propagation',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':1.25})
        environment,context=package_check_environment(design,'wire',.25e-9,.2e-9)
        self.assertEqual(environment['network']['network']['package_r'],1.25)
        self.assertEqual(context['design_provenance'],design.provenance())
        self.assertEqual(context['resolved_configuration']['reference_hz'],2.5e9)


class ReferenceStartupSnapshotTests(unittest.TestCase):
    def test_startup_uses_supplied_guard_and_separates_current_hypothesis(self):
        from selected_lifecycle import reference_startup_screen
        design=load_design()
        contract=design.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        variant=DesignDefinition.from_documents(contract,design.architecture)
        report=reference_startup_screen(contract,design=variant)
        self.assertEqual(report['assigned_guard_s'],30e-6)
        rows=report['cases']
        self.assertEqual(rows[0]['design_provenance'],variant.provenance())
        self.assertNotEqual(rows[3]['design_provenance']['design_fingerprint'],variant.fingerprint)
        self.assertEqual(rows[3]['reference_limit_a'],rows[0]['reference_limit_a']/4)
        self.assertGreater(rows[1]['maximum_native_code_error_lsb'],50)
        self.assertLessEqual(rows[0]['maximum_native_code_error_lsb'],2)


class HandoverSnapshotTests(unittest.TestCase):
    def test_revision_wired_clock_probe_binds_tx_peer_context(self):
        from selected_revision_check import revision_clock_environment
        from wired_lock_probe import peer_for_environment
        design=load_design()
        environment,context=revision_clock_environment(design,'wire',2.5e9)
        self.assertEqual(context['resolved_configuration']['direction'],'tx')
        peer,edges,ideal=peer_for_environment(environment,0)
        self.assertEqual(peer['probe_context'],context)
        self.assertEqual(len(edges),len(ideal))

    def test_wired_peer_rejects_wrong_rate_or_foreign_context_before_clock_work(self):
        from baseline_envelope import configured_environment
        from wired_lock_probe import peer_for_environment
        from unittest.mock import patch
        from copy import deepcopy
        design=load_design()
        configurations=[design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                            sample_divider=64,pga_gain_db=39),
                        design.configure(engine='wire',direction='tx',reference_hz=1.25e9,host_divider=8)]
        with patch('wired_lock_probe.DeliveredClock') as clock:
            for config in configurations:
                with self.assertRaisesRegex(ValueError,'2.5 Gb/s TX configuration'):
                    peer_for_environment(configured_environment(config),0)
            environment=configured_environment(design.configure(engine='wire',direction='tx',
                reference_hz=2.5e9,host_divider=8))
            with self.assertRaisesRegex(ValueError,'matching probe context'):
                peer_for_environment(environment,0)
            environment['probe_context']=dict(design_provenance=design.provenance(),
                resolved_configuration=deepcopy(environment['resolved_configuration']))
            environment['probe_context']['resolved_configuration']['reference_hz']=1.25e9
            with self.assertRaisesRegex(ValueError,'matching probe context'):
                peer_for_environment(environment,0)
            environment['resolved_configuration']['design_fingerprint']='foreign'
            with self.assertRaisesRegex(ValueError,'conflicts with environment provenance'):
                peer_for_environment(environment,0)
            clock.assert_not_called()

    def test_wired_peer_does_not_alias_input_provenance(self):
        from baseline_envelope import configured_environment
        from wired_lock_probe import peer_for_environment
        design=load_design()
        environment=configured_environment(design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8))
        environment['probe_context']=dict(design_provenance=design.provenance(),
            resolved_configuration=environment['resolved_configuration'],probe_assumptions={'label':['original']})
        peer,_,_=peer_for_environment(environment,0)
        peer['probe_context']['probe_assumptions']['label'].append('changed')
        self.assertEqual(environment['probe_context']['probe_assumptions']['label'],['original'])
        environment['probe_context']['resolved_configuration']['reference_hz']=1.
        self.assertEqual(peer['probe_context']['resolved_configuration']['reference_hz'],2.5e9)

    def test_handover_preserves_endpoint_uncertainty_without_aliasing(self):
        from selected_lifecycle import handover_environment,handover_context,capture_context
        from design_definition import Scenario
        design=load_design()
        scenario=Scenario().override(reason='Adverse endpoint return path',package_return_inductance_h=2e-9)
        environment=handover_environment(design,'rf',2.4e9,scenario=scenario)
        context=handover_context(design,[environment])
        self.assertEqual(context['scenario_overrides'],scenario.record())
        saved=context['environment_conditions'][0]
        self.assertEqual(saved['scenario_overrides'],scenario.record())
        self.assertEqual(saved['reference_package_parameters'],design.architecture['model_assumptions']['reference_input_package']['parameters'])
        environment['scenario_overrides'].clear()
        environment['reference_package_parameters']['bond_l_h']=9e-9
        self.assertEqual(saved['scenario_overrides'],scenario.record())
        self.assertEqual(saved['reference_package_parameters']['bond_l_h'],2e-9)
        continuation=capture_context(design,{'handover':context},operation='test')
        self.assertEqual(continuation['input_capture_context']['handover']['environment_conditions'],context['environment_conditions'])
        foreign=dict(environment,design_provenance={})
        with self.assertRaisesRegex(ValueError,'endpoint conflicts'):
            handover_context(design,[foreign])

    def test_handover_endpoints_share_hypothetical_circuit(self):
        from selected_lifecycle import handover_environment,handover_context
        design=load_design().hypothetical(reason='Handover feed-resistance propagation',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':1.25})
        environments=[handover_environment(design,'rf',2.4e9),handover_environment(design,'wire',2.5e9)]
        context=handover_context(design,environments)
        for environment in environments:
            self.assertEqual(environment['network']['network']['package_r'],1.25)
            self.assertEqual(environment['design_provenance'],design.provenance())
        self.assertEqual([c['inventory_mode'] for c in context['resolved_configurations']],['rf_rx','wired'])
        self.assertEqual(context['design_provenance'],design.provenance())

    def test_handover_rejects_conflicting_contract_before_simulation(self):
        from selected_lifecycle import switching_load_handover,full_package_handover
        design=load_design()
        contract=design.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']*=2
        for function in (switching_load_handover,full_package_handover):
            with self.assertRaises(ValueError):function(contract,design=design)


class FiniteReplaySnapshotTests(unittest.TestCase):
    def test_independent_words_conserve_bits_at_shared_host_rate(self):
        from selected_lifecycle import finite_sar_transport
        design=load_design()
        capture=dict(converter_stages=[dict(stage='independent_word_fixture',
            sample_times_s=[i/37.5e6 for i in range(16)],words=[[i,-i] for i in range(16)],
            final_state={'end_time_s':1e-6})])
        result=finite_sar_transport(design.contract,capture,design=design)
        row=result['stages'][0]
        self.assertEqual(row['design_provenance'],design.provenance())
        self.assertEqual(row['delivered_words'],38)
        self.assertEqual(row['discarded']['rx_bits'],4)
        self.assertEqual(row['d2h_word_hz'],150e6)
        self.assertTrue(row['unready_replay_rejected'])
        self.assertIn('Unbound word fixture',result['input_capture_scope'])
        # A wired-to-RF capture contains only the destination ADC stage.
        before=design.configure(engine='wire',direction='tx',reference_hz=2.5e9,host_divider=8)
        after=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=128,pga_gain_db=39)
        from baseline_envelope import configured_environment
        from selected_lifecycle import handover_context
        from design_definition import Scenario
        scenario=Scenario().override(host_output_load_f=2e-12,reason='Replay host-load uncertainty')
        capture.update(handover_context(design,[configured_environment(c,scenario) for c in (before,after)]))
        stage=capture['converter_stages'][0];stage['stage']='after'
        stage['sample_times_s']=[.4e-6+i/(2.426e9/128) for i in range(16)]
        stage['final_state']['end_time_s']=1.5e-6
        result=finite_sar_transport(design.contract,capture,design=design,
            rx_cutoff_hz=5e6,tx_cutoff_hz=5e6)
        row=result['stages'][0]
        self.assertEqual(row['resolved_configuration'],after.record())
        self.assertEqual(row['scenario_overrides'],scenario.record())
        self.assertEqual(row['flow']['required_bps'],(2.426e9/128)*24)
        self.assertEqual(row['delivered_words'],38)
        self.assertEqual(row['discarded']['rx_bits'],4)

    def test_replay_rejects_capture_from_other_design(self):
        from selected_lifecycle import finite_sar_transport
        design=load_design()
        other=design.hypothetical(reason='Different reference current',changes={
            'blocks.refbuf.parameters.source_limit_a':.0005})
        with self.assertRaisesRegex(ValueError,'capture conflicts'):
            finite_sar_transport(design.contract,dict(design_provenance=other.provenance()),design=design)
        with self.assertRaisesRegex(ValueError,'requires endpoint configurations'):
            finite_sar_transport(design.contract,dict(design_provenance=design.provenance()),design=design)


class ExtendedReplaySnapshotTests(unittest.TestCase):
    def test_operating_summary_preserves_inputs_and_rejects_foreign_captures(self):
        import copy
        from selected_lifecycle import analog_operating_summary
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=64,pga_gain_db=39)
        # Synthetic measurements test pooling/provenance, not RF performance.
        trace=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
            scenario_overrides=[{'reason':'Synthetic summary fixture'}],sources_sha256={},
            lifecycle_stimuli={'turnaround':True,'stress_ripple_peak_v':.01},
            shared_supply_stress=dict(source_offset_v=0.,ripple_peak_v=.01,ripple_hz=1e6,delay_sensitivity_multiplier=1.),
            stages=[dict(rf_quality=dict(evm_rms=.1,bpsk_errors=0,evaluated_bits=10,real_preamble_acquisition=False)),
                dict(tx_rf_port=dict(data_interval_power={'mean_load_power_dbm':0.},quality={'evm_rms':.2},
                    nominal_gain_requirement=4.5,host_preparation={'native_complex_code_peak':50.}))])
        report={name:copy.deepcopy(trace) for name in ('joined_tx_operating_envelope','joined_wired_recovery')}
        result=analog_operating_summary(report,design=design)
        self.assertEqual(result['observed_rx_evm_interval'],[.1,.1])
        saved=result['input_capture_context']['joined_wired_recovery']['lifecycle_stimuli']
        self.assertEqual(saved,trace['lifecycle_stimuli'])
        saved['stress_ripple_peak_v']=.02
        self.assertEqual(report['joined_wired_recovery']['lifecycle_stimuli']['stress_ripple_peak_v'],.01)
        self.assertEqual(result['input_capture_context']['joined_wired_recovery']['resolved_configuration'],config.record())
        del report['joined_wired_recovery']['design_provenance']
        with self.assertRaisesRegex(ValueError,'supplied design'):analog_operating_summary(report,design=design)
        other=design.hypothetical(reason='Different summary circuit',changes={'blocks.lna.parameters.noise_figure_db':8.})
        report['joined_wired_recovery']['design_provenance']=other.provenance()
        with self.assertRaisesRegex(ValueError,'supplied design'):analog_operating_summary(report,design=design)

        # The known-tone summary must retain the same capture boundary.
        from selected_lifecycle import turnaround_signal_audit
        import numpy as np
        times=np.arange(200)*1e-8
        words=np.column_stack((1000*np.cos(2*np.pi*1e6*times),
                               1000*np.sin(2*np.pi*1e6*times))).tolist()
        tone=copy.deepcopy(trace)
        tone['stages']=[dict(host_received_iq=dict(nominal_sample_times_s=times.tolist(),
            signed_iq_words=words),direction_actions=[dict(gated_at_s=.4e-6),dict(ready_at_s=.8e-6)])]
        measured=turnaround_signal_audit(tone,design=design)
        self.assertLess(measured['held_out_resumed']['normalized_residual_rms'],1e-12)
        self.assertAlmostEqual(measured['fitted_gain_ratio_after_to_before'],1.)
        self.assertEqual(measured['input_capture_context']['turnaround']['resolved_configuration'],config.record())
        self.assertEqual(measured['input_capture_context']['turnaround']['scenario_overrides'],trace['scenario_overrides'])
        for provenance in (None,other.provenance()):
            invalid=copy.deepcopy(tone)
            if provenance is None:del invalid['design_provenance']
            else:invalid['design_provenance']=provenance
            with self.assertRaisesRegex(ValueError,'supplied design'):
                turnaround_signal_audit(invalid,design=design)

    def test_frozen_tx_audits_preserve_capture_conditions(self):
        from selected_lifecycle import tx_local_supply_requirement,tx_power_goal_audit
        design=load_design();architecture=design.architecture
        config=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64)
        trace=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
            scenario_overrides=[dict(parameter='package_return_inductance_h',value=2e-9,
                                     reason='Adverse package fixture')],
            stages=[{},dict(tx_rf_port=dict(electrical={'minimum_supply_v':3.},
                nominal_gain_requirement=4.5,
                data_interval_power={'mean_load_power_w':.001,'peak_to_mean_load_power_db':3.},
                amplitude_requirement=dict(driver_parameters=architecture['blocks']['rfdriver']['parameters'],
                    output_parameters=architecture['model_assumptions']['rf_output']['parameters'])))])
        for audit in (tx_local_supply_requirement,tx_power_goal_audit):
            result=audit(design.contract,trace,design=design)
            recorded=result['input_capture_context']['tx']
            self.assertEqual(result['design_provenance'],design.provenance())
            self.assertEqual(recorded['resolved_configuration'],config.record())
            self.assertEqual(recorded['scenario_overrides'],trace['scenario_overrides'])
            recorded['scenario_overrides'][0]['value']=9e-9
            self.assertEqual(trace['scenario_overrides'][0]['value'],2e-9)
            # Metadata binding must not relax the existing missing-capture guard.
            with self.assertRaisesRegex(ValueError,'requires a capture'):
                audit(design.contract,{'stages':trace['stages']},design=design)

        import copy
        baseline=tx_power_goal_audit(design.contract,trace,design=design)
        variant=design.hypothetical(reason='Inverse TX gain reference check',changes={
            'blocks.rfdriver.parameters.gain_reference_v':3.0})
        changed=copy.deepcopy(trace)
        changed['design_provenance']=variant.provenance()
        changed['resolved_configuration']=variant.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=64).record()
        changed['stages'][1]['tx_rf_port']['amplitude_requirement']['driver_parameters']=variant.architecture['blocks']['rfdriver']['parameters']
        result=tx_power_goal_audit(variant.contract,changed,design=variant)
        # Inverse nominal-gain requirements scale with reference voltage,
        # while forward gain scales inversely. This is not a waveform re-run.
        for key in ('nominal_gain_lower_necessary','nominal_gain_upper_sufficient_headroom'):
            self.assertAlmostEqual(result['fixed_gain_screen'][key]/baseline['fixed_gain_screen'][key],3./3.3)
        self.assertAlmostEqual(result['fixed_gain_screen']['optimistic_power_margin_db'],
                               baseline['fixed_gain_screen']['optimistic_power_margin_db'])

    def test_capture_conditions_survive_replay_without_aliasing_or_invented_defaults(self):
        from selected_lifecycle import continuation_context,replay_context
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.484e9,sample_divider=64,pga_gain_db=39)
        capture=dict(design_provenance=design.provenance(),resolved_configuration=config.record(),
            scenario_overrides=[dict(parameter='package_return_inductance_h',value=2e-9,
                                     reason='Adverse package fixture')],
            scenario_assumptions={'temperature_c':25.},
            lifecycle_stimuli={'turnaround':True,'stress_ripple_peak_v':.01})
        for factory in (continuation_context,lambda d,c:replay_context(d,c,1e6,3e6)):
            result=factory(design,{'rx':capture,'primitive':{}})
            recorded=result['input_capture_context']['rx']
            self.assertEqual(recorded,capture)
            self.assertIsNot(recorded['scenario_overrides'],capture['scenario_overrides'])
            self.assertEqual(result['input_capture_context']['primitive'],{})
            self.assertEqual(result['input_capture_scope']['primitive'],'unbound_numerical_fixture')
            recorded['scenario_overrides'][0]['value']=9e-9
            self.assertEqual(capture['scenario_overrides'][0]['value'],2e-9)

            import copy
            for field in ('sample_hz','control_hz','h2d_word_hz'):
                damaged=copy.deepcopy(capture)
                damaged['resolved_configuration'][field]*=2
                with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Recorded configuration differs'):
                    factory(design,{'rx':damaged})
            named=copy.deepcopy(capture)
            named['resolved_configurations']={'rf_rx':named.pop('resolved_configuration')}
            restored=factory(design,{'rx':named})
            self.assertEqual(restored['input_capture_context']['rx']['resolved_configurations'],
                             {'rf_rx':config.record()})
            named['resolved_configurations']['rf_rx']['sample_hz']*=2
            self.assertEqual(restored['input_capture_context']['rx']['resolved_configurations'],
                             {'rf_rx':config.record()})
            with self.assertRaisesRegex(ValueError,'Recorded configuration differs'):
                factory(design,{'rx':named})
            endpoints=[copy.deepcopy(capture['resolved_configuration'])]
            endpoints[0]['host_word_hz']*=2
            for records in (endpoints,[],None):
                damaged=copy.deepcopy(capture)
                del damaged['resolved_configuration']
                damaged['resolved_configurations']=records
                with self.subTest(endpoints=records),self.assertRaises(ValueError):
                    factory(design,{'rx':damaged})

    def test_extended_independent_words_survive_rearm_without_frame_truncation(self):
        import numpy as np
        from selected_lifecycle import extended_sar_transport
        design=load_design()
        times=np.arange(.4e-6,24.94e-6,64/2.484e9)
        fixture=dict(numerical_feedback_converged=True,final_carrier_hz=2.484e9,
            direction='rf_retune',pre_transition_monitor_times_s=np.arange(0,.2e-6,64/2.4e9),
            converter_stages=[dict(sample_times_s=times,words=[[i%200,-(i%200)] for i in range(len(times))],
                final_state={'end_time_s':25e-6},supply_acceptance=dict(invalid_points=0,evaluated_interval_v=[3.,3.]))])
        result=extended_sar_transport(design.contract,fixture,design=design)
        self.assertEqual(result['input_capture_scope']['retune'],'unbound_numerical_fixture')
        self.assertEqual(result['resolved_configuration']['reference_hz'],2.484e9)
        self.assertEqual(result['eligible_converter_samples']*24,result['delivered_host_words']*10+result['discarded']['rx_bits'])
        self.assertTrue(result['stale_callbacks_rejected'])
        self.assertGreater(result['delivered_host_words'],0)
        endpoints=[design.configure(engine='rf',direction='rx',reference_hz=f,
            sample_divider=128,pga_gain_db=39) for f in (2.4e9,2.484e9)]
        fixture.update(design_provenance=design.provenance(),
            resolved_configurations=[c.record() for c in endpoints])
        fixture['pre_transition_monitor_times_s']=np.arange(0,.2e-6,128/2.4e9)
        times=np.arange(.4e-6,24.94e-6,128/2.484e9)
        fixture['converter_stages'][0].update(sample_times_s=times,
            words=[[i%200,-(i%200)] for i in range(len(times))])
        result=extended_sar_transport(design.contract,fixture,design=design,
            rx_cutoff=5e6,tx_cutoff=5e6)
        self.assertEqual(result['resolved_configuration'],endpoints[1].record())
        self.assertEqual(result['flow']['required_bps'],2.484e9/128*24)
        self.assertEqual(result['eligible_converter_samples']*24,
            result['delivered_host_words']*10+result['discarded']['rx_bits'])

    def test_recovery_rejects_conflicting_capture_before_replay(self):
        from selected_lifecycle import fault_recovery_transport
        design=load_design()
        other=design.hypothetical(reason='Other recovery circuit',changes={'blocks.refbuf.parameters.source_limit_a':.0005})
        with self.assertRaisesRegex(ValueError,'capture conflicts'):
            fault_recovery_transport(design.contract,{}, {},dict(design_provenance=other.provenance()),{},design=design)
        # Missing identity must not downgrade a chip capture to a primitive.
        for malformed in (dict(design_provenance=None),dict(design_provenance={}),
                          dict(resolved_configuration={}),dict(resolved_configurations=[]),
                          dict(environment_conditions=[])):
            with self.subTest(capture=malformed):
                with self.assertRaisesRegex(ValueError,'requires design provenance'):
                    fault_recovery_transport(design.contract,{}, {},malformed,{},design=design)
        from selected_lifecycle import continuation_context
        context=continuation_context(design,{'primitive':{'times_s':[0.,1.]}})
        self.assertEqual(context['input_capture_scope']['primitive'],'unbound_numerical_fixture')
        from unittest.mock import patch
        from behavioral import BehavioralChip
        observed=[];original=BehavioralChip.configure_numeric
        def configure(chip,**kwargs):
            observed.append(kwargs)
            return original(chip,**kwargs)
        configs=[design.configure(engine='rf',direction='rx',reference_hz=f,
            sample_divider=128,pga_gain_db=39) for f in (2.426e9,2.484e9)]
        stage={'converter':{'evaluated_supply_interval_v':[3.,3.]}}
        retune=dict(design_provenance=design.provenance(),
            resolved_configurations=[c.record() for c in configs],
            final_carrier_hz=2.484e9,converter_stages=[stage,stage])
        recovery=dict(numerical_feedback_converged=True,**stage)
        rejected=fault_recovery_transport(design.contract,retune,
            dict(recovery,numerical_feedback_converged=False),{}, {},design=design,
            rx_cutoff=5e6,tx_cutoff=5e6)
        self.assertEqual(rejected['verdict'],'rejected_analog_trajectory')
        self.assertEqual(rejected['resolved_configuration'],configs[1].record())
        with self.assertRaisesRegex(ValueError,'nonempty endpoint configurations'):
            fault_recovery_transport(design.contract,dict(retune,resolved_configurations=None),
                dict(recovery,numerical_feedback_converged=False),{}, {},design=design,
                rx_cutoff=5e6,tx_cutoff=5e6)
        # Stop at the qualification boundary after executing real configuration.
        with patch.object(BehavioralChip,'configure_numeric',configure), \
             patch('selected_lifecycle.converter_qualification_events',
                   side_effect=RuntimeError('qualification boundary')):
            with self.assertRaisesRegex(RuntimeError,'qualification boundary'):
                fault_recovery_transport(design.contract,retune,recovery,{'trace':{}},{},
                    design=design,rx_cutoff=5e6,tx_cutoff=5e6)
        self.assertEqual(observed[0]['rf']['lo_hz'],2.426e9)
        self.assertEqual(observed[0]['rf']['sample_hz'],2.426e9/128)
        self.assertEqual(observed[0]['rf']['lo_divider'],128)


class RetuneSnapshotTests(unittest.TestCase):
    def test_changed_threshold_reaches_retained_converter_sample_edges(self):
        import numpy as np
        from unittest.mock import patch
        from selected_lifecycle import retained_sar_retune
        from converter_dynamics import paired_sar
        threshold=.035;frequency=2.4e9;amplitude=.3;target=.9
        design=load_design().hypothetical(reason='Threshold and reference target propagation through retained SAR',changes={
            'model_assumptions.reference_input_acceptance.parameters.threshold_v':threshold,
            'blocks.refbuf.parameters.target_v':target})
        times=np.arange(0,.8e-6,5e-12)
        # Independent sinusoidal forcing isolates crossing/divider propagation.
        # No shared-package performance is claimed for this synthetic capture.
        capture=dict(times_s=times,clock_forcing={'carrier_hz':frequency},
            effective_input_v=amplitude*np.sin(2*np.pi*frequency*times),
            rail_v=np.full_like(times,3.),reference_v=np.full_like(times,target),delay_s=np.zeros_like(times))
        capture.update(design_provenance=design.provenance(),resolved_configurations=[
            design.configure(engine='rf',direction='rx',reference_hz=frequency,
                sample_divider=128,pga_gain_db=39).record() for _ in range(2)])
        from baseline_envelope import configured_environment
        from selected_lifecycle import handover_context
        from converter_dynamics import load_response
        from design_definition import Scenario
        scenario=Scenario().override(package_return_inductance_h=2e-9,
            reason='Retained recharge package uncertainty')
        endpoints=[configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=frequency,sample_divider=128,pga_gain_db=39),scenario) for _ in range(2)]
        capture.update(handover_context(design,endpoints))
        observed=[];feedback=[]
        def solve(*args,**kwargs):
            sample_times=args[2]
            expected=np.full_like(sample_times,target)
            if feedback:
                previous=feedback[-1]
                expected+=target*np.interp(sample_times,previous['times_s'],previous['reference_fraction'])
            np.testing.assert_allclose(args[3](sample_times),expected,rtol=0,atol=2e-15)
            answer=paired_sar(*args,**kwargs)
            observed.append(answer)
            return answer
        def respond(*args,**kwargs):
            answer=load_response(*args,**kwargs)
            feedback.append(answer[0])
            return answer
        with patch('converter_dynamics.paired_sar',side_effect=solve) as solver, \
             patch('converter_dynamics.load_response',side_effect=respond) as recharge:
            result=retained_sar_retune(design.contract,design=design,
                package_capture=({'direction':'rf_retune','design_provenance':design.provenance(),
                    'resolved_configurations':capture['resolved_configurations']},capture))
        # The first iteration has no recharge overlay: compare actual solver
        # sample times with analytical sine roots, independently of grid interpolation.
        self.assertEqual(recharge.call_args.args[1]['return_l_h'],2e-9)
        self.assertEqual(result['scenario_overrides'],scenario.record())
        from selected_lifecycle import captured_endpoint_environments
        from check_contract import verify_reported_configuration
        configs=[verify_reported_configuration(design,r) for r in capture['resolved_configurations']]
        rebuilt=captured_endpoint_environments(design,configs,capture,result)
        from copy import deepcopy
        broken=deepcopy(endpoints)
        broken[1]['control_hz']/=2
        with self.assertRaisesRegex(ValueError,'Control clock conflicts'):
            handover_context(design,broken)
        self.assertTrue(all(e['network']['return_l_h']==2e-9 for e in rebuilt))
        from copy import deepcopy
        conflicting=deepcopy(result)
        conflicting['environment_conditions'][1]['scenario_overrides'][0]['value']=3e-9
        with self.assertRaisesRegex(ValueError,'endpoint conditions conflict'):
            captured_endpoint_environments(design,configs,capture,conflicting)
        for missing in (False,True):
            conflicting=deepcopy(result)
            condition=conflicting['environment_conditions'][1]
            if missing:del condition['reference_package_parameters']
            else:condition['reference_package_parameters']['bond_l_h']*=2
            with self.subTest(missing_physical_parameter=missing):
                with self.assertRaisesRegex(ValueError,'physical condition conflicts'):
                    captured_endpoint_environments(design,configs,capture,conflicting)
        for key in ('board_source_v','rf_receive_supply_parameters','wired_supply_gain_parameters','host_source_parameters','control_hz','transport_parameters'):
            for missing in (False,True):
                conflicting=deepcopy(result)
                condition=conflicting['environment_conditions'][1]
                if missing:del condition[key]
                elif key in ('board_source_v','control_hz'):condition[key]=3.0
                else:condition[key]={name:3.0 for name in condition[key]}
                with self.subTest(key=key,missing=missing),self.assertRaisesRegex(ValueError,'physical condition conflicts'):
                    captured_endpoint_environments(design,configs,capture,conflicting)
        displacement=np.arcsin(threshold/amplitude)/(2*np.pi*frequency)
        for call,index in zip(solver.call_args_list[:2],(128,1088)):
            samples=call.args[2]
            self.assertAlmostEqual(samples[0],index/frequency+displacement,delta=.05e-12)
            np.testing.assert_allclose(np.diff(samples),128/frequency,rtol=0.,atol=.1e-12)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['input_capture_scope'],'design_bound')
        self.assertEqual(result['resolved_configurations'],capture['resolved_configurations'])
        self.assertEqual(result['environment_conditions'][0]['reference_acceptance_parameters']['threshold_v'],threshold)
        self.assertEqual(result['environment_conditions'][0]['reference_supply_parameters']['target_v'],target)
        self.assertGreater(len(feedback),1)
        for index in range(0,len(observed),2):
            before,after=observed[index:index+2]
            self.assertEqual(after[1]['initial_reference_v'],before[2]['final_state']['reference_v'])
            self.assertLess(abs(after[1]['reference_charge_balance_residual_c']),1e-20)

    def test_retune_passes_changed_converter_parameters_to_solver(self):
        import numpy as np
        from unittest.mock import patch
        from selected_lifecycle import retained_sar_retune
        design=load_design().hypothetical(reason='Verify retune converter parameter binding',changes={
            'blocks.refbuf.parameters.source_limit_a':.0005})
        times=np.arange(0,.8e-6,.05e-9)
        capture=dict(design_provenance=design.provenance(),times_s=times,
            clock_forcing={'carrier_hz':2.484e9},effective_input_v=.3*np.sin(2*np.pi*2.4e9*times),
            rail_v=np.full_like(times,3.),reference_v=np.ones_like(times),delay_s=np.zeros_like(times))
        package=dict(direction='rf_retune',design_provenance=design.provenance())
        with self.assertRaisesRegex(ValueError,'requires endpoint configurations'):
            retained_sar_retune(design.contract,design=design,package_capture=(package,capture))
        package['resolved_configurations']=[design.configure(engine='rf',direction='rx',
            reference_hz=f,sample_divider=64,pga_gain_db=42).record() for f in (2.4e9,2.484e9)]
        with patch('converter_dynamics.paired_sar',side_effect=RuntimeError('solver entry captured')) as solver:
            with self.assertRaisesRegex(RuntimeError,'solver entry captured'):
                retained_sar_retune(design.contract,design=design,package_capture=(package,capture))
        self.assertEqual(solver.call_args.kwargs['parameters'].reference_limit_a,.0005)

    def test_retune_rejects_mismatched_package(self):
        from selected_lifecycle import retained_sar_retune
        design=load_design()
        other=design.hypothetical(reason='Different package circuit',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':1.})
        with self.assertRaisesRegex(ValueError,'Package capture conflicts'):
            retained_sar_retune(design.contract,design=design,
                package_capture=(dict(design_provenance=other.provenance()),{}))


class ClockLossSnapshotTests(unittest.TestCase):
    def test_clock_loss_rejects_foreign_package_before_computing(self):
        from selected_lifecycle import package_clock_loss,clock_loss_sar_continuation
        design=load_design()
        other=design.hypothetical(reason='Foreign continuation circuit',changes={
            'blocks.refbuf.parameters.source_limit_a':.0005})
        foreign=dict(design_provenance=other.provenance())
        with self.assertRaisesRegex(ValueError,'capture conflicts'):
            package_clock_loss(design.contract,foreign,design=design)
        with self.assertRaisesRegex(ValueError,'capture conflicts'):
            clock_loss_sar_continuation(design.contract,{},foreign,{}, {},design=design)
        configs=[design.configure(engine='rf',direction='rx',reference_hz=f,
            sample_divider=128,pga_gain_db=39).record() for f in (2.4e9,2.484e9)]
        retune=dict(design_provenance=design.provenance(),resolved_configurations=configs)
        stale=design.configure(engine='rf',direction='rx',reference_hz=2.484e9,
            sample_divider=64,pga_gain_db=39).record()
        for key,value in (('resolved_configuration',stale),
                          ('resolved_configurations',[configs[0],stale])):
            with self.subTest(field=key):
                fault=dict(design_provenance=design.provenance(),**{key:value})
                with self.assertRaisesRegex(ValueError,'endpoint settings conflict'):
                    clock_loss_sar_continuation(design.contract,{},fault,retune,{},design=design)

    def test_continuation_identifies_each_unbound_input(self):
        from selected_lifecycle import continuation_context
        design=load_design()
        result=continuation_context(design,dict(package={'design_provenance':design.provenance()},converter={}))
        self.assertEqual(result['input_capture_scope'],dict(package='design_bound',converter='unbound_numerical_fixture'))


class HandoverPackageOverrideTests(unittest.TestCase):
    def test_same_explicit_package_corner_reaches_both_endpoints(self):
        from selected_lifecycle import handover_environment
        from design_definition import Scenario
        design=load_design()
        scenario=Scenario().override(reason='Adverse handover package',
            package_return_inductance_h=2e-9,die_decoupling_esl_h=1e-9)
        for mode,carrier in [('rf',2.4e9),('wire',2.5e9)]:
            environment=handover_environment(design,mode,carrier,scenario=scenario)
            self.assertEqual(environment['network']['return_l_h'],2e-9)
            self.assertEqual(environment['network']['network']['die_esl'],1e-9)
            self.assertEqual(environment['design_provenance'],design.provenance())
        self.assertEqual(design.architecture['blocks']['power']['parameters']['shared_return_l_h'],.25e-9)


class LifecycleSnapshotForwardingTests(unittest.TestCase):
    def test_retained_lifecycle_constructs_chip_from_supplied_transport(self):
        from unittest.mock import patch
        import selected_lifecycle as lifecycle
        design=load_design();contract=design.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        design=DesignDefinition.from_documents(contract,design.architecture)
        captured=[]
        class ReachedChip(Exception):pass
        def construct(assumptions):
            captured.append(assumptions)
            raise ReachedChip
        with patch.object(lifecycle,'BehavioralChip',side_effect=construct):
            with self.assertRaises(ReachedChip):
                lifecycle.ownership_load_trace(design.contract,design=design)
        self.assertEqual(len(captured),1)
        self.assertEqual(captured[0].startup_s,30e-6)
        self.assertEqual(captured[0].d2h_clock_scale,(2.4e9/16)/312.5e6)

        import tempfile,json
        import baseline_envelope as b
        hashes=b.baseline_source_hashes()
        for dependency in ('system_model/architecture_fast/design_definition.py',
                'verification/usb_selected_timing.py','system_model/architecture_fast/direct_stream.py',
                'verification/wired_lock_probe.py','verification/wideband_packet.py'):
            self.assertIn(dependency,hashes)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'evidence').mkdir()
            path=root/'evidence/selected-lifecycle.json'
            for option,key,runner in (('--ownership','ownership_load_trace','ownership_load_trace'),
                               ('--ownership-usb','ownership_usb_trace','ownership_load_trace'),
                               ('--ownership-diagnostics','ownership_diagnostic_trace','ownership_load_trace'),
                               ('--wired-recovery','loaded_wired_recovery','loaded_wired_recovery'),
                               ('--wired-noise-attribution','wired_noise_attribution','ownership_load_trace'),
                               ('--joint-wired-recovery','joined_wired_recovery','ownership_load_trace'),
                               ('--joint-tx-envelope','joined_tx_operating_envelope','ownership_load_trace'),
                               ('--ripple-envelope','joined_ripple_envelope','ownership_load_trace')):
                with patch.object(b,'P',root),patch.object(lifecycle,'load_design',return_value=design), \
                     patch('sys.argv',['selected_lifecycle.py',option]), \
                     patch.object(lifecycle,runner,return_value={'status':'completed_scoped_lifecycle','shared_supply_stress':{},
                         'stages':[dict(engine='fixture',directions=[],fault=None,rf_quality={},
                             tx_rf_port=None,wired_analog_cdr={},wired_tx_electrical={}) for _ in range(7)]}) as run, \
                     patch('builtins.print'), \
                     patch.object(b,'baseline_source_hashes',side_effect=[hashes,hashes]):
                    lifecycle.main()
                self.assertIs(run.call_args.kwargs['design'],design)
                self.assertEqual(json.loads(path.read_text())[key]['sources_sha256'],hashes)
                previous=path.read_text();changed=dict(hashes)
                changed['system_model/architecture_fast/design_definition.py']='changed'
                with patch.object(b,'P',root),patch.object(lifecycle,'load_design',return_value=design), \
                     patch('sys.argv',['selected_lifecycle.py',option]), \
                     patch.object(lifecycle,runner,return_value={'status':'completed_scoped_lifecycle','shared_supply_stress':{},
                         'stages':[dict(engine='fixture',directions=[],fault=None,rf_quality={},
                             tx_rf_port=None,wired_analog_cdr={},wired_tx_electrical={}) for _ in range(7)]}), \
                     patch.object(b,'baseline_source_hashes',side_effect=[hashes,changed]):
                    with self.assertRaisesRegex(RuntimeError,'Sources changed'):
                        lifecycle.main()
                self.assertEqual(path.read_text(),previous)
            with patch.object(b,'P',root),patch.object(lifecycle,'load_design',return_value=design), \
                 patch('sys.argv',['selected_lifecycle.py']), \
                 patch.object(lifecycle,'monitor_recovery_campaign',return_value=[]) as monitor, \
                 patch.object(b,'baseline_source_hashes',side_effect=[hashes,changed]):
                with self.assertRaisesRegex(RuntimeError,'Sources changed during lifecycle campaign'):
                    lifecycle.main()
            monitor.assert_called_once_with(design)
            self.assertEqual(path.read_text(),previous)

    def test_bound_lifecycle_functions_do_not_reload_converter_defaults(self):
        import ast
        import selected_lifecycle
        tree=ast.parse(Path(selected_lifecycle.__file__).read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotEqual(node.func.attr,'selected_converter_parameters',
                    'Lifecycle must resolve converters from its supplied design')


    def test_campaign_orchestrators_forward_their_snapshot_to_design_aware_children(self):
        # Structural guard complements parameter-propagation tests: these two
        # orchestrators must not reopen specs between capture and continuation.
        import ast
        import selected_lifecycle,selected_revision_check
        checked=0
        for module in (selected_lifecycle,selected_revision_check):
            tree=ast.parse(Path(module.__file__).read_text())
            factories={n.name for n in tree.body if isinstance(n,ast.FunctionDef)
                       and any(a.arg=='design' for a in n.args.kwonlyargs)}
            for parent in tree.body:
                if not isinstance(parent,ast.FunctionDef) or parent.name not in ('main','retained_sar_refinement'):
                    continue
                for call in ast.walk(parent):
                    if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id not in factories:
                        continue
                    with self.subTest(parent=parent.name,child=call.func.id,line=call.lineno):
                        forwarded=next((k.value for k in call.keywords if k.arg=='design'),None)
                        self.assertIsInstance(forwarded,ast.Name)
                        self.assertEqual(forwarded.id,'design')
                    checked+=1
        self.assertGreater(checked,30)

    def test_refinement_starts_with_the_supplied_hypothetical_snapshot(self):
        from unittest.mock import patch
        from selected_lifecycle import retained_sar_refinement
        design=load_design().hypothetical(reason='Refinement snapshot propagation',
            changes={'model_assumptions.paired_adc.parameters.aperture_rms_s':12e-12})
        class ReachedChild(Exception):pass
        def child(contract,**kwargs):
            self.assertIs(kwargs['design'],design)
            self.assertEqual(contract,design.contract)
            raise ReachedChild
        with patch('selected_lifecycle.full_package_handover',side_effect=child), \
             patch('design_definition.load_design',side_effect=AssertionError('unexpected reload')):
            with self.assertRaises(ReachedChild):
                retained_sar_refinement(design.contract,design=design)


class MonitorRecoverySnapshotTests(unittest.TestCase):
    def test_shared_startup_moves_both_complete_recovery_timelines(self):
        from unittest.mock import patch
        from selected_lifecycle import monitor_recovery_campaign,wired_tx_lifecycle
        baseline=load_design()
        for guard in (20e-6,30e-6):
            contract=baseline.contract
            contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=guard
            design=DesignDefinition.from_documents(contract,baseline.architecture)
            used=[]
            def observe(environment,*args,**kwargs):
                result=wired_tx_lifecycle(environment,*args,**kwargs)
                used.append(environment)
                return result
            with patch('design_definition.load_design',side_effect=AssertionError('unexpected reload')), \
                 patch('selected_lifecycle.wired_tx_lifecycle',side_effect=observe):
                rows=monitor_recovery_campaign(design)
            self.assertEqual({r['engine'] for r in rows},{'rf','wire'})
            for row in rows:
                self.assertEqual(row['design_provenance'],design.provenance())
                self.assertTrue(row['payload_prefix_correct'])
                self.assertTrue(row['stale_epoch_rejected'])
                self.assertAlmostEqual(row['injected_clock_gap_s'][0],guard+2e-6)
                self.assertAlmostEqual(row['recovered_at_s'],2*guard+3.1e-6)
                self.assertEqual(row['queue_depth_bits'],contract['transport']['scheduling']['ingress_bits_per_source'])
                self.assertGreater(row['delivered_words_after_recovery'],0)
                if row['wired_tx_lifecycle']:
                    self.assertEqual(row['wired_tx_lifecycle'][0]['fault'],'reference_lost')
                    self.assertIsNone(row['wired_tx_lifecycle'][1]['fault'])
                    before,after=row['wired_tx_lifecycle']
                    self.assertIsNot(before['resolved_configuration'],after['resolved_configuration'])
                    before['resolved_configuration']['host_word_hz']=1.
                    self.assertEqual(after['resolved_configuration']['host_word_hz'],312.5e6)
                    used[0]['resolved_configuration']['host_word_hz']=2.
                    used[0]['scenario_overrides'].append({'reason':'Post-run caller edit'})
                    self.assertEqual(after['resolved_configuration']['host_word_hz'],312.5e6)
                    self.assertEqual(after['scenario_overrides'],[])


    def test_monitor_fixture_uses_its_actual_rf_divider(self):
        from selected_lifecycle import monitor_recovery_environment
        design=load_design()
        environment,context=monitor_recovery_environment(design,'rf')
        self.assertEqual(context['resolved_configuration']['sample_divider'],256)
        self.assertEqual(context['resolved_configuration']['sample_hz'],9.375e6)
        self.assertEqual(environment['resolved_configuration'],context['resolved_configuration'])
        self.assertEqual(context['design_provenance'],design.provenance())

    def test_wired_monitor_allows_the_rx_and_tx_diagnostics(self):
        from selected_lifecycle import monitor_recovery_environment
        environment,context=monitor_recovery_environment(load_design(),'wire')
        self.assertEqual(context['resolved_configuration']['direction'],'duplex')
        self.assertEqual(context['resolved_configuration']['host_word_hz'],312.5e6)
        self.assertIn('uniform peer',context['probe_assumptions']['wired_rx_clock'])


class USBSupplySnapshotTests(unittest.TestCase):
    def test_supply_probe_uses_usb_owner_budget_and_host_rate(self):
        import baseline_envelope as b
        design=load_design()
        environment,context=b.usb_supply_environment(design)
        self.assertEqual(context['resolved_configuration']['inventory_mode'],'usb')
        self.assertEqual(context['resolved_configuration']['reference_hz'],480e6)
        self.assertEqual(environment['transport_parameters']['h2d_word_hz'],100e6)
        ledger=b.partitioned_dc_ledger(environment,dict(link_r_ohm=1e-5))
        self.assertAlmostEqual(ledger['total_chip_supply_current_a'],sum(environment['inventory_current_a'].values()))
        self.assertEqual(context['design_provenance'],design.provenance())


class ClockScreenSnapshotTests(unittest.TestCase):
    def test_clock_screen_keeps_changed_package_and_owner_limits(self):
        import baseline_envelope as b
        design=load_design().hypothetical(reason='Clock screen feed probe',changes={
            'blocks.power.parameters.reduced_pdn_model.network.package_r':1.})
        for mode,carrier in [('rf',2.4e9),('wire',2.5e9)]:
            environment,context=b.clock_screen_environment(design,mode,carrier)
            self.assertEqual(context['design_provenance'],design.provenance())
            self.assertEqual(environment['network']['network']['package_r'],1.)
            with self.assertRaisesRegex(ValueError,'Internal pulse mean exceeds owner DC budget'):
                b.internal_switching_sources([dict(owner='core',mean_a=1.,event_hz=100e6,tau_s=.2e-9,harmonics=32)],
                    owner_current_a=environment['inventory_current_a'])

        from unittest.mock import patch
        variant=design.hypothetical(reason='Return topology source propagation',changes={
            'blocks.board.parameters.analog_supply_v':3.267,
            'blocks.board.parameters.digital_supply_v':3.267})
        solve=b.partitioned_return_solution
        class ReachedDC(Exception):pass
        def observe(frequency,candidate,injection,**kwargs):
            if frequency==0.:
                # Sum of nodal injections is the Norton source: all chip
                # current loads cancel against their explicit return currents.
                self.assertAlmostEqual(sum(injection),3.267/candidate['network']['feed_r'])
                raise ReachedDC
            return solve(frequency,candidate,injection,**kwargs)
        with patch.object(b,'partitioned_return_solution',side_effect=observe):
            with self.assertRaises(ReachedDC):
                b.return_partition_campaign(variant.contract,design=variant)


class DecouplingSnapshotTests(unittest.TestCase):
    def test_circuit_and_parasitic_changes_are_separate(self):
        import baseline_envelope as b
        design=load_design()
        environment,context=b.decoupling_environment(design,'rf',2.4e9,1e-9,1.,400e-12)
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(len(context['scenario_overrides']),1)
        self.assertEqual(environment['network']['network']['die_c'],1e-9)
        self.assertEqual(environment['network']['network']['die_esr'],1.)
        self.assertEqual(environment['network']['network']['die_esl'],400e-12)
        self.assertEqual(design.architecture['blocks']['power']['parameters']['reduced_pdn_model']['network']['die_c'],500e-12)


class HostSpectrumRateBindingTests(unittest.TestCase):
    def test_usb_spectrum_and_dc_charge_follow_actual_host_rate(self):
        import baseline_envelope as b
        design=load_design()
        environment,_=b.usb_supply_environment(design)
        spectrum=environment['host_spectrum']
        self.assertEqual(spectrum['h2d_word_hz'],100e6)
        self.assertEqual(spectrum['d2h_word_hz'],100e6)
        self.assertEqual(spectrum['h2d_ports'][0]['frequency_hz'],50e6)
        # Eleven alternating inputs, 7 pC each, at 100 Mwords/s.
        expected=.0077
        self.assertAlmostEqual(spectrum['chip_h2d_internal_mean_a'],expected)
        self.assertAlmostEqual(environment['ledger']['h2d_internal_current_within_host_a'],expected)
        ledger=b.partitioned_dc_ledger(environment,dict(link_r_ohm=1e-5))
        self.assertAlmostEqual(ledger['h2d_internal_current_within_host_a'],expected)
        self.assertAlmostEqual(ledger['total_chip_supply_current_a'],sum(environment['inventory_current_a'].values()))
        self.assertLess(abs(ledger['power_balance_residual_w']),1e-10)

        for key in ('analog_supply_v','digital_supply_v'):
            for value in (None,0.,-1.,True,float('nan'),float('inf')):
                architecture=design.architecture
                if value is None:del architecture['blocks']['board']['parameters'][key]
                else:architecture['blocks']['board']['parameters'][key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)
        # A distinct host-output swing changes both pulse charge and width.
        import cmath,math
        contract=design.contract
        contract['physical_services']['host_output']['voltage_v']=3.0
        changed_design=DesignDefinition.from_documents(contract,design.architecture)
        changed_env,_=b.usb_supply_environment(changed_design)
        self.assertEqual(changed_env['host_spectrum']['output_voltage_v'],3.0)
        frequency=50e6;charge=6e-12*3.;width=charge/.01
        # Fourier integral of a rectangular 10 mA pulse, independently of
        # the helper's sinc implementation; first harmonic has no internal term.
        expected=2*.01*frequency*(1-cmath.exp(-2j*math.pi*frequency*width))/(2j*math.pi*frequency)
        self.assertAlmostEqual(b.partitioned_d2h_sources(changed_env)[frequency][2],expected)
        self.assertNotEqual(b.partitioned_d2h_sources(environment)[frequency][2],expected)
        self.assertEqual(changed_env['host_spectrum']['h2d_ports'],environment['host_spectrum']['h2d_ports'])
        from robustness_envelope import shared_return_transfer
        network=environment['network']
        transfer=shared_return_transfer(frequency,return_r=network['return_r_ohm'],
            return_l=network['return_l_h'],**network['network'])
        nominal_charge=6e-12*3.3
        nominal=2*.01*frequency*(1-cmath.exp(-2j*math.pi*frequency*nominal_charge/.01))/(2j*math.pi*frequency)
        delta=expected-nominal
        self.assertAlmostEqual(b.pad_ground_tones(changed_env)[frequency]-
            b.pad_ground_tones(environment)[frequency],delta*transfer['ground_ohm'])
        def rail_tone(env):
            item=next(t for t in env['host_spectrum']['tones'] if t['frequency_hz']==frequency)
            return item['clock_rail_voltage_peak_v']*cmath.exp(1j*item['voltage_phase_rad'])
        self.assertAlmostEqual(rail_tone(changed_env)-rail_tone(environment),
            delta*transfer['differential_ohm'])
        del changed_env['host_spectrum']['output_voltage_v']
        for consume in (b.partitioned_d2h_sources,b.partitioned_host_sources,b.pad_ground_tones):
            with self.assertRaisesRegex(ValueError,'missing output_voltage_v'):
                consume(changed_env)
        # One common-feed source must follow the supplied board hypothesis.
        variant=design.hypothetical(reason='Board DC source sensitivity',changes={
            'blocks.board.parameters.analog_supply_v':3.267,
            'blocks.board.parameters.digital_supply_v':3.267})
        changed,_=b.usb_supply_environment(variant)
        shifted=b.partitioned_dc_ledger(changed,dict(link_r_ohm=1e-5))
        self.assertAlmostEqual(shifted['source_v'],3.267)
        self.assertAlmostEqual(shifted['local_payload_clock_core_rail_v']-
                               ledger['local_payload_clock_core_rail_v'],-.033)
        self.assertLess(abs(shifted['power_balance_residual_w']),1e-10)
        del changed['board_source_v']
        with self.assertRaisesRegex(ValueError,'missing board source'):
            b.partitioned_dc_ledger(changed,dict(link_r_ohm=1e-5))
        split=design.hypothetical(reason='Unsupported split-feed control',changes={
            'blocks.board.parameters.analog_supply_v':3.267})
        with self.assertRaisesRegex(ValueError,'equal analog and digital'):
            b.usb_supply_environment(split)


class HostChargeOwnershipTests(unittest.TestCase):
    def test_legacy_factory_cannot_silently_ignore_a_charge_override(self):
        from baseline_envelope import inventory_environment
        design=load_design()
        for key in ('h2d_internal_charge_c','d2h_internal_charge_c'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'conflicts with design snapshot'):
                inventory_environment(design.contract,design.architecture,'wire',2.5e9,312.5e6,
                                      design=design,**{key:14e-12})
            environment=inventory_environment(design.contract,design.architecture,'wire',2.5e9,312.5e6,
                                              design=design,**{key:7e-12})
            recorded='internal_charge_c' if key.startswith('h2d') else key
            self.assertEqual(environment['host_spectrum'][recorded],7e-12)

    def test_changed_charge_reaches_spectrum_and_dc_without_changing_host_budget(self):
        import baseline_envelope as b
        design=load_design()
        variant=design.hypothetical(reason='Double input transition charge',changes={
            'model_assumptions.host_switching.parameters.h2d_internal_charge_c':14e-12})
        base,_=b.usb_supply_environment(design)
        changed,_=b.usb_supply_environment(variant)
        self.assertAlmostEqual(changed['host_spectrum']['chip_h2d_internal_mean_a'],.0154)
        self.assertAlmostEqual(changed['ledger']['h2d_internal_current_within_host_a'],.0154)
        self.assertEqual(base['inventory_current_a'],changed['inventory_current_a'])
        self.assertAlmostEqual(changed['host_spectrum']['h2d_ports'][1]['chip_internal_current_peak_a'],
                               2*base['host_spectrum']['h2d_ports'][1]['chip_internal_current_peak_a'])

        # Reject damaged bound records at every common harmonic entry point.
        import copy
        for key in ('output_cap_f','d2h_internal_charge_c','internal_charge_c',
                    'd2h_word_hz','h2d_word_hz','d2h_internal_tau_s'):
            for value in (None,True,-1.,float('nan'),float('inf')):
                damaged=copy.deepcopy(base)
                if value is None:del damaged['host_spectrum'][key]
                else:damaged['host_spectrum'][key]=value
                for consume in (b.pad_ground_tones,b.partitioned_d2h_sources,b.partitioned_host_sources):
                    with self.subTest(key=key,value=value,consumer=consume.__name__), \
                         self.assertRaisesRegex(ValueError,'Design-bound host source'):
                        consume(damaged)
        # Independent mathematical source examples retain their own values.
        primitive={'host_spectrum':{'output_cap_f':0.}}
        self.assertEqual(b.host_source_parameters(primitive),primitive['host_spectrum'])

    def test_missing_host_charge_fails_at_snapshot_creation(self):
        design=load_design()
        for direction in ('h2d','d2h'):
            key=direction+'_internal_charge_c'
            architecture=design.architecture
            del architecture['model_assumptions']['host_switching']['parameters'][key]
            with self.subTest(direction=direction),self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)
            for value in (-1.,True,float('nan'),float('inf')):
                architecture=design.architecture
                architecture['model_assumptions']['host_switching']['parameters'][key]=value
                with self.subTest(direction=direction,value=value),self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)


class RevisionCommandSnapshotTests(unittest.TestCase):
    def test_feed_candidate_and_package_corner_remain_distinct(self):
        from selected_revision_check import revision_clock_environment,revision_ble_options
        design=load_design().hypothetical(reason="Aperture ownership control",changes={
            "model_assumptions.paired_adc.parameters.aperture_rms_s":13e-12})
        environment,context=revision_clock_environment(design,'rf',2.426e9,
            return_l=2e-9,die_esl=1e-9,feed_candidate=True)
        self.assertEqual(environment['network']['network']['package_r'],1.)
        self.assertEqual(environment['network']['return_l_h'],2e-9)
        self.assertNotEqual(context['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertEqual(len(context['scenario_overrides']),2)
        self.assertEqual(context['resolved_configuration']['pga_gain_db'],42)
        options=revision_ble_options(environment,512)
        self.assertEqual(options['aperture_rms_s'],13e-12)
        self.assertEqual(options['mixer_substeps'],512)
        del environment['adc_noise_parameters']['aperture_rms_s']
        with self.assertRaises(KeyError):revision_ble_options(environment,512)


class CampaignSnapshotPropagationTests(unittest.TestCase):
    def test_recursive_campaigns_preserve_hypothesis_without_reload(self):
        from unittest.mock import patch
        import baseline_envelope as b
        design=load_design().hypothetical(reason='Snapshot forwarding regression',
            changes={'blocks.rfdriver.parameters.bias_current_a':.027})
        # Ownership check only; no payload-performance assertion.
        with patch.object(b,'load_design',side_effect=AssertionError('Unexpected disk reload')), patch.object(b,'network_cases',return_value=()):
            for name in ('narrowband_exchange','converter_feedback','transmitter_wake_campaign','wired_transmit_campaign','wired_recovery_campaign'):
                with self.subTest(campaign=name):
                    self.assertEqual(getattr(b,name)(design.contract,design=design)['design_provenance'],design.provenance())

    def test_usb_pad_snapshot_changes_physical_transfer(self):
        from unittest.mock import patch
        import numpy as np
        import baseline_envelope as b
        design=load_design();environment,_=b.usb_supply_environment(design)
        architecture=design.architecture;increment=.5e-12
        architecture['pad_behavioral_contract']['shared_wired_network']['base_shunt_cap_f_per_leg']+=increment
        architecture['blocks']['wirepad']['parameters']['capacitance_f_per_leg']+=increment
        changed=DesignDefinition.from_documents(design.contract,architecture)
        other,_=b.usb_supply_environment(changed)
        np.testing.assert_allclose(np.asarray(other['wired_pad_capacitance_f'])-environment['wired_pad_capacitance_f'],np.eye(2)*increment,rtol=1e-12,atol=1e-26)
        with patch.object(b,'load_design',side_effect=AssertionError('Unexpected disk reload')):
            first=b.hs_pad_transfer(2e9,capacitance_f=environment['wired_pad_capacitance_f'])
            second=b.hs_pad_transfer(2e9,capacitance_f=other['wired_pad_capacitance_f'])
            self.assertGreater(np.linalg.norm(first['ground_board']-second['ground_board']),1e-4)
            b.usb_static_output(other,other['ledger'],levels=(1,0),load_ohm=15000.)
            b.usb_hs_output(other,other['ledger'])
        self.assertEqual(other['design_provenance']['design_fingerprint'],changed.fingerprint)

    def test_packet_transmission_rejects_wrong_direction_and_rate(self):
        import baseline_envelope as b
        from ble_packet import transmitted_scan_response
        design=load_design()
        rx=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=256,pga_gain_db=39)
        tx=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=256)
        request=dict(response=dict(reply_armed=False),settings=dict(sample_hz=tx.sample_hz))
        environment=b.configured_environment(tx)
        result=transmitted_scan_response(request,environment,design.contract)
        self.assertFalse(result['transmitted'])
        self.assertEqual(result['resolved_configuration'],tx.record())
        with self.assertRaisesRegex(ValueError,'RF TX configuration'):
            transmitted_scan_response(request,b.configured_environment(rx),design.contract)
        with self.assertRaisesRegex(ValueError,'sample rate'):
            transmitted_scan_response(dict(request,settings=dict(sample_hz=1e6)),environment,design.contract)

    def test_invalid_converter_allocations_fail_at_design_load(self):
        design=load_design()
        cases=(('model_assumptions.paired_dac.parameters.enob',11.),
               ('model_assumptions.paired_dac.parameters.enob',True),
               ('model_assumptions.paired_dac.parameters.aperture_rms_s',-1e-12),
               ('blocks.dac_i.parameters.native_bits',10.5),
               ('blocks.dac_i.parameters.native_bits',13),
               ('blocks.dac_i.parameters.sample_rate_max_hz',0),
               ('blocks.dac_q.parameters.differential_peak_v',0))
        for path,value in cases:
            with self.subTest(path=path,value=value):
                architecture=design.architecture;node=architecture
                parts=path.split('.')
                for part in parts[:-1]:node=node[part]
                node[parts[-1]]=value
                with self.assertRaises(ValueError):
                    DesignDefinition.from_documents(design.contract,architecture)

    def test_shared_output_distortion_reaches_port_voltage(self):
        import numpy as np
        from baseline_envelope import configured_environment
        from selected_rf import transmit_output
        design=load_design().hypothetical(reason='Analytical real-tone distortion example',changes={
            'model_assumptions.rf_output.parameters.gain_imbalance_db':0.,
            'model_assumptions.rf_output.parameters.phase_error_deg':0.,
            'model_assumptions.rf_output.parameters.lo_feedthrough':0.,
            'model_assumptions.rf_output.parameters.cubic':.2})
        environment=configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=64))
        driver=environment['transmitter_parameters']['rfdriver']
        port,_,clipped=transmit_output(np.full(4,.2+0j),np.full(4,3.3),np.zeros(4),
            nominal_gain=1.,driver_parameters=driver,
            output_parameters=environment['rf_output_parameters'])
        # Independent real scalar cubic followed by a resistive divider.
        expected=.2*(1-.2*.2**2)*driver['load_ohm_differential']/(driver['source_r_ohm_differential']+driver['load_ohm_differential'])
        np.testing.assert_allclose(port['envelope_v'],expected,rtol=1e-12,atol=1e-15)
        self.assertFalse(np.any(clipped))

    def test_shared_environment_cannot_fall_back_to_primitive_tx_or_sar(self):
        import baseline_envelope as b
        design=load_design()
        environment=b.configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=64))
        del environment['resolved_configuration']
        with self.assertRaisesRegex(ValueError,'resolved configuration'):
            b.wideband_transmit(environment)
        del environment['converter_parameters']
        del environment['inventory_current_report']
        with self.assertRaisesRegex(ValueError,'missing selected converter'):
            b.environment_converter_parameters(environment)

    def test_receiver_inventory_noise_and_temperature_reach_waveform(self):
        import baseline_envelope as b
        from design_definition import Scenario
        design=load_design().hypothetical(reason='Receiver noise allocation propagation',changes={
            'blocks.lna.parameters.noise_figure_db':7.25,
            'blocks.lna.parameters.iip3_dbm':-2.,
            'blocks.adc_i.parameters.enob_target':7.,
            'blocks.adc_q.parameters.enob_target':7.})
        environment=b.configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.484e9,sample_divider=64,pga_gain_db=42),Scenario(assumptions={'temperature_c':25}))
        result=b.wideband_receive(environment,oversample=128)
        self.assertEqual(result['chip_input_noise_figure_db'],7.25)
        self.assertEqual(result['input_iip3_dbm'],-2.)
        self.assertEqual(result['enob_hypothesis'],7.)
        self.assertAlmostEqual(result['thermal_noise_temperature_k'],298.15)
        self.assertEqual(result['scenario_assumptions'],{'temperature_c':25})
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertFalse(result['receiver_diagnostic_overrides'])

    def test_receiver_adapters_reject_unrepresented_paired_allocations(self):
        import baseline_envelope as b
        from ble_packet import joined_scan_request
        from unittest.mock import patch
        design=load_design()
        for changes,expected in (
                ({'blocks.adc_i.parameters.transport_bits':13,
                  'blocks.adc_q.parameters.transport_bits':13},'transport'),
                ({'blocks.adc_q.parameters.enob_target':7.},'matched I/Q ENOB')):
            with self.subTest(changes=changes):
                variant=design.hypothetical(reason='Unsupported receiver adapter allocation',changes=changes)
                environment=b.configured_environment(variant.configure(engine='rf',direction='rx',
                    reference_hz=2.426e9,sample_divider=64,pga_gain_db=39))
                with patch('selected_rf.he_source',side_effect=AssertionError('waveform started')):
                    with self.assertRaisesRegex(ValueError,expected):
                        b.wideband_receive(environment)
                with patch('ble_packet.gfsk',side_effect=AssertionError('waveform started')):
                    with self.assertRaisesRegex(ValueError,expected):
                        joined_scan_request(environment,variant.contract)

    def test_packet_paths_reject_contract_from_another_design(self):
        import baseline_envelope as b
        from ble_packet import joined_scan_request,transmitted_scan_response,response_budget
        from design_definition import validate_contract_provenance
        design=load_design()
        changed=design.contract
        changed['generic_configuration_target']['tx_port_power_goal']['mean_load_power_dbm']+=1
        for direction,call in (
                ('rx',lambda e:joined_scan_request(e,changed)),
                ('tx',lambda e:transmitted_scan_response({},e,changed)),
                ('rx',lambda e:response_budget({}, {},e,changed,advertiser_address=b''))):
            with self.subTest(direction=direction,call=call):
                environment=b.configured_environment(design.configure(engine='rf',direction=direction,
                    reference_hz=2.426e9,sample_divider=256,
                    **({'pga_gain_db':39} if direction=='rx' else {})))
                with self.assertRaisesRegex(ValueError,'Contract conflicts'):
                    call(environment)
        validate_contract_provenance(dict(reversed(list(design.contract.items()))),design.provenance())
        validate_contract_provenance({'independent':'mathematical fixture'},None)
        with self.assertRaisesRegex(ValueError,'Contract conflicts'):
            validate_contract_provenance(design.contract,{})

    def test_lna_selection_reaches_frontend_with_independent_voltage_ratio(self):
        import numpy as np
        import baseline_envelope as b
        from selected_rf import receive_frontend,receiver_lna_gain
        design=load_design();outputs=[]
        for gain in (10,20):
            config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
                sample_divider=64,pga_gain_db=39,lna_gain_db=gain)
            environment=b.configured_environment(config)
            self.assertEqual(config.record()['lna_gain_db'],gain)
            values,_=receive_frontend(np.ones(8),np.arange(8)/1e8,
                np.full(8,3.3),np.zeros(8),sample_hz=1e8,blocker_dbm=None,
                early_gain_db=receiver_lna_gain(environment))
            outputs.append(values)
        np.testing.assert_allclose(outputs[1]/outputs[0],np.sqrt(10),rtol=1e-12)
        changed=design.hypothetical(reason='Changed legal LNA gain inventory',changes={
            'blocks.lna.parameters.gain_db':[-6,0,10]})
        config=changed.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=64,pga_gain_db=39)
        self.assertEqual(config.lna_gain_db,10)
        self.assertEqual(config.record()['design_fingerprint'],changed.fingerprint)
