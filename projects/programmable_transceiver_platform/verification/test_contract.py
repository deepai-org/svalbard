"""Negative checks for pin, direction and capacity mistakes in the contract."""
import copy
import json
import unittest
import sys
from check_contract import CONTRACT, check, resource_ledger, assembly_ledger, operating_clock_ledger, periodic_stream_bound, milestone_coverage

sys.path.insert(0,str(CONTRACT.parent.parent/'system_model/architecture_fast'))
from design_definition import load_design

TEST_DESIGN_ROLES = {
    'ContractTests': ('shared_design', 'Shared contract/schema and reconstructed configuration guards; deliberately corrupted copies are rejection controls.'),
    'ContractTests.test_simulation_audit_distinguishes_primitive_tests_and_integration': ('independent_fixture', 'Synthetic source files test inventory classification, not chip behavior.'),
    'ContractTests.test_rf_chain_audit_rejects_missing_or_fabricated_success': ('independent_fixture', 'Synthetic missing/fabricated evidence checks acceptance integrity.'),
    'ContractTests.test_review_evidence_reports_changed_missing_and_unmanifested_sources': ('independent_fixture', 'Synthetic files and hash changes test evidence freshness.'),
    'ContractTests.test_service_bound_prices_gaps_and_rejects_persistent_overload': ('independent_fixture', 'Independently assigned stream rates, frame sizes and service gaps test queue arithmetic.'),
}

class ContractTests(unittest.TestCase):
    def test_saved_configuration_recomputes_derived_values(self):
        from check_contract import verify_reported_configuration
        design=load_design()
        configuration=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=64,pga_gain_db=39)
        self.assertEqual(verify_reported_configuration(design,configuration.record()).record(),configuration.record())
        for key,value in (('sample_hz',1.),('host_word_hz',1.),('inventory_mode','rf_tx'),
                          ('design_fingerprint','wrong'),('pga_gain_db',54.)):
            record=configuration.record();record[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):verify_reported_configuration(design,record)
        with self.assertRaises(ValueError):verify_reported_configuration(design,None)

    def test_reported_variant_reconstructs_from_shared_parent_and_rejects_tampering(self):
        from check_contract import reconstruct_reported_design
        base=load_design()
        variant=base.hypothetical(reason='Assigned receiver uncertainty',changes={
            'blocks.lna.parameters.noise_figure_db':8.})
        variant=variant.hypothetical(reason='Assigned comparator uncertainty',changes={
            'model_assumptions.paired_sar_comparator.parameters.tau_s':100e-12})
        for design in (base,variant):
            self.assertEqual(reconstruct_reported_design(base,design.provenance()).provenance(),design.provenance())
        for field in ('before','after'):
            provenance=variant.provenance()
            provenance['circuit_experiments'][0]['changes'][0][field]+=1
            with self.assertRaises(ValueError):reconstruct_reported_design(base,provenance)
        provenance=variant.provenance()
        provenance['circuit_experiments'][0]['parent_design_fingerprint']='wrong'
        with self.assertRaises(ValueError):reconstruct_reported_design(base,provenance)
        provenance=variant.provenance();provenance['circuit_experiments']=[]
        with self.assertRaises(ValueError):reconstruct_reported_design(base,provenance)

    def setUp(self):
        self.c = load_design().contract

    def test_simulation_audit_distinguishes_primitive_tests_and_integration(self):
        from check_contract import simulation_design_audit
        from tempfile import TemporaryDirectory
        from pathlib import Path
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'verification').mkdir();(root/'system_model').mkdir()
            (root/'verification/bench.py').write_text('def bench():\n    a=inventory_environment(c,a)\n    p=SharedWiredPad()\n')
            (root/'verification/test_math.py').write_text('def test_limit():\n    x=SARParameters()\n    y=ClientBench()\n')
            report=simulation_design_audit(root)
            self.assertEqual(report['non_test_file_construction_counts']['independent_pad_constructor'],1)
            self.assertNotIn('independent_converter_constructor',report['non_test_file_construction_counts'])
            self.assertEqual(report['construction_counts']['independent_converter_constructor'],1)
            self.assertEqual(report['construction_counts']['shared_design_wifi_fixture'],1)
            self.assertEqual(report['static_test_method_count'],1)
            method=report['test_methods'][0]
            self.assertEqual(method['scope'],'test_limit')
            self.assertEqual(method['tracked_constructors'],['ClientBench','SARParameters'])
            self.assertEqual(method['classification'],'requires_semantic_review')
            self.assertEqual(report['sites'][0]['scope'],'bench')
            self.assertFalse(report['parse_errors'])
            (root/'verification/test_wrapped.py').write_text(
                'class Example:\n'
                '    def setUp(self):\n        self.design=load_design()\n'
                '    def helper(self):\n        return configured_environment(self.design)\n'
                '    def test_wrapped(self):\n        self.helper()\n')
            wrapped=next(x for x in simulation_design_audit(root)['test_methods']
                         if x['scope']=='Example.test_wrapped')
            self.assertEqual(wrapped['tracked_constructors'],[])
            self.assertEqual(wrapped['local_helper_scopes'],['Example.helper','Example.setUp'])
            self.assertEqual(wrapped['locally_reachable_constructors'],['configured_environment','load_design'])
            self.assertEqual(wrapped['classification'],'requires_semantic_review')
            path=root/'verification/test_wrapped.py'
            path.write_text("TEST_DESIGN_ROLES = {'Example': ('independent_fixture', 'Numerical examples'), "
                "'Example.test_wrapped': ('shared_design', 'Uses shared setup and helper')}\n"+path.read_text())
            declared=simulation_design_audit(root)
            wrapped=next(x for x in declared['test_methods'] if x['scope']=='Example.test_wrapped')
            self.assertEqual(wrapped['declared_role'],'shared_design')
            self.assertEqual(wrapped['role_source'],'Example.test_wrapped')
            self.assertEqual(wrapped['classification'],'requires_semantic_review')
            self.assertEqual(declared['declared_role_counts'],{'unclassified':1,'shared_design':1})
            # A class default entirely shadowed by method declarations is stale.
            self.assertEqual(declared['role_declaration_errors'][0]['scope'],'Example')
            path.write_text("TEST_DESIGN_ROLES = {'Example': ('unknown', '')}\nclass Example:\n    def test_one(self):pass\n")
            invalid=simulation_design_audit(root)
            self.assertEqual(invalid['declared_role_counts'],{'unclassified':2})
            self.assertEqual(len(invalid['role_declaration_errors']),1)
        # Keep the repository inventory complete as tests are added or renamed.
        # This proves explicit intent coverage, not downstream design binding.
        current=simulation_design_audit()
        self.assertEqual(current['parse_errors'],[])
        self.assertEqual(current['role_declaration_errors'],[])
        self.assertEqual(current['declared_role_counts'].get('unclassified',0),0)


    def test_rf_chain_audit_rejects_missing_or_fabricated_success(self):
        from check_contract import rf_chain_evidence_audit
        from tempfile import TemporaryDirectory
        from pathlib import Path
        import hashlib
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'evidence').mkdir()
            self.assertFalse(rf_chain_evidence_audit(root)['first_version_complete'])
            source=root/'source.py';source.write_text('original')
            report={'rf_chain_first_version':{'cases':{'wideband_nominal':{
                'status':'conditional_operating_point','accepted':True,
                'sources_sha256':{'source.py':hashlib.sha256(source.read_bytes()).hexdigest()}}}}}
            (root/'evidence/selected-revision-check.json').write_text(json.dumps(report))
            audit=rf_chain_evidence_audit(root)
            self.assertTrue(audit['cases'][0]['sources_match'])
            self.assertFalse(audit['cases'][0]['conditional_point'])
            self.assertFalse(audit['first_version_complete'])
            source.write_text('changed')
            self.assertFalse(rf_chain_evidence_audit(root)['cases'][0]['sources_match'])

    def test_rf_acceptance_requires_recorded_converter_and_mode_inventory(self):
        from check_contract import rf_chain_evidence_audit
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from dataclasses import asdict
        from converter_dynamics import parameters_from_inventory
        import hashlib
        import sys
        sys.path.insert(0,str(CONTRACT.parent.parent/'system_model/architecture_fast'))
        from rf_quality_budget import current_allocation
        design=load_design();architecture=design.architecture
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'evidence').mkdir();(root/'spec').mkdir()
            (root/'verification').mkdir()
            (root/'spec/analog-architecture.json').write_text(json.dumps(architecture))
            (root/'spec/contract.json').write_text(json.dumps(self.c))
            for filename in ('baseline_envelope.py','converter_dynamics.py','selected_revision_check.py'):
                (root/'verification'/filename).write_text('# explicit provenance fixture\n')
            sources={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest()
                     for folder in ('verification','spec') for f in (root/folder).iterdir()}
            current=current_allocation(architecture,'rf_tx',branch='external_rf_clock')
            row=dict(name='tx_nominal',mode='tx',status='clock_rejected',accepted=False,
                design_provenance=design.provenance(),
                resolved_configuration=design.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64).record(),
                inventory_current_ma=current['total_ma'],sources_sha256=sources,
                design_binding=dict(inventory_mode='rf_tx',current_report=current,
                    converter_parameters=asdict(parameters_from_inventory(architecture))))
            def audit(value):
                (root/'evidence/selected-revision-check.json').write_text(json.dumps(
                    {'rf_chain_first_version':{'cases':{'tx_nominal':value}}}))
                return rf_chain_evidence_audit(root)['cases'][0]
            result=audit(row)
            self.assertTrue(result['sources_match'])
            self.assertTrue(result['selected_design_binding_matches'])
            self.assertTrue(result['declared_variant_binding_matches'])
            self.assertFalse(result['conditional_point'])
            self.assertFalse(result['nominal_evidence_usable'])
            wrong=copy.deepcopy(row);wrong['resolved_configuration']['host_word_hz']=1.
            self.assertFalse(audit(wrong)['resolved_configuration_verified'])
            self.assertFalse(audit(wrong)['nominal_evidence_usable'])
            wrong=copy.deepcopy(row);del wrong['design_provenance']
            self.assertFalse(audit(wrong)['selected_design_binding_matches'])
            wrong=copy.deepcopy(row);wrong['design_provenance']['design_fingerprint']='foreign'
            self.assertFalse(audit(wrong)['shared_design_provenance_matches'])
            wrong=copy.deepcopy(row);wrong['design_binding']['converter_parameters']['diagnostic_input_cap_f']=0.
            self.assertFalse(audit(wrong)['selected_design_binding_matches'])
            self.assertFalse(audit(wrong)['declared_variant_binding_matches'])
            wrong=copy.deepcopy(row);wrong['design_binding']['inventory_mode']='rf_rx'
            self.assertFalse(audit(wrong)['selected_design_binding_matches'])
            wrong=copy.deepcopy(row);del wrong['sources_sha256']['spec/analog-architecture.json']
            self.assertTrue(audit(wrong)['sources_match'])
            self.assertFalse(audit(wrong)['selected_design_binding_matches'])
            wrong=copy.deepcopy(row);del wrong['design_binding']
            self.assertFalse(audit(wrong)['selected_design_binding_matches'])
            variant=design.hypothetical(reason='Different SAR switch resistance',changes={
                'model_assumptions.paired_sar.parameters.sample_resistance_ohm':
                    2*architecture['model_assumptions']['paired_sar']['parameters']['sample_resistance_ohm']})
            alternate=copy.deepcopy(row)
            alternate['design_provenance']=variant.provenance()
            alternate['resolved_configuration']=variant.configure(engine='rf',direction='tx',reference_hz=2.426e9,sample_divider=64).record()
            self.assertFalse(audit(alternate)['declared_variant_binding_matches'])
            alternate['design_binding']['converter_parameters']=asdict(parameters_from_inventory(variant.architecture))
            verified=audit(alternate)
            self.assertTrue(verified['declared_variant_binding_matches'])
            self.assertFalse(verified['selected_design_binding_matches'])
            self.assertFalse(verified['conditional_point'])
            # Independent 1 dBm observation must be compared with the declared
            # target, including a hypothetical 3 dBm requirement.
            measured=copy.deepcopy(row)
            measured.update(loaded_mean_power_dbm=1.,checks={'mixer_headroom':True},
                clock={'ledger':{'owner_current_a':{'rf':.04}}},
                transmitter=dict(observed_rail_interval_v=[3.,3.3],
                    electrical=dict(checks={'fixture':True},driver_bias_current_a=.01),
                    driver_current_clipped_samples_during_source=0,host_input_clipped_components=0,
                    observation=dict(bpsk_errors=0,evm_rms=.01),reactive_load={}))
            self.assertTrue(audit(measured)['independent_checks']['target_power'])
            target=design.hypothetical(reason='Independent TX target audit control',changes={
                'blocks.rfdriver.parameters.target_mean_power_dbm':3.})
            measured['design_provenance']=target.provenance()
            measured['resolved_configuration']=target.configure(engine='rf',direction='tx',
                reference_hz=2.426e9,sample_divider=64).record()
            self.assertFalse(audit(measured)['independent_checks']['target_power'])

    def test_rf_acceptance_requires_recorded_shared_pga_headroom(self):
        from check_contract import rf_chain_evidence_audit
        from tempfile import TemporaryDirectory
        from pathlib import Path
        design=load_design();architecture=design.architecture
        peak=architecture['blocks']['pga_i']['parameters']['differential_peak_limit_v']
        # Synthetic measurements exercise audit logic, not receiver performance.
        adc=dict(evaluated_supply_interval_v=[3.,3.3],reference_interval_v=[1.,1.],
            schedule_margin_s=1e-9,actual_completion_margin_s=1e-9,reference_with_bias_peak_a=.001)
        frontend=dict(observed_rail_interval_v=[3.,3.3],
            frontend_nonlinearity={'within_assigned_small_compression_range':True},
            gain_cases=[dict(adc=adc,pga_clipped_samples_during_source=0)])
        row=dict(status='synthetic_audit_fixture',mode='wideband',wanted_dbm=-60.,blocker_dbm=-40.,
            receiver=dict(payload_correct=True,analog=dict(receiver=frontend,numerical_feedback_converged=True)))
        with TemporaryDirectory() as directory:
            root=Path(directory);(root/'spec').mkdir();(root/'evidence').mkdir()
            (root/'spec/analog-architecture.json').write_text(json.dumps(architecture))
            def audit(value):
                if value is None:frontend.pop('pga_nominal_peak_limit_v',None)
                else:frontend['pga_nominal_peak_limit_v']=value
                (root/'evidence/selected-revision-check.json').write_text(json.dumps(
                    {'rf_chain_first_version':{'cases':{'wideband_nominal':row}}}))
                return rf_chain_evidence_audit(root)['cases'][0]['independent_checks']
            self.assertTrue(audit(peak)['adc_headroom'])
            for value in (None,peak/2,float('nan'),True):
                with self.subTest(value=value):
                    result=audit(value)
                    self.assertFalse(result['pga_headroom_design_binding'])
                    self.assertFalse(result['adc_headroom'])
            # Keep the independently chosen 1 V ADC bound, but change the
            # declared headroom law: 0.8*3.3/2.5 exceeds that bound.
            (root/'spec/contract.json').write_text(json.dumps(design.contract))
            row['design_provenance']=design.provenance()
            row['resolved_configuration']=design.configure(engine='rf',direction='rx',
                reference_hz=2.426e9,sample_divider=64,pga_gain_db=39).record()
            self.assertTrue(audit(peak)['adc_headroom'])
            variant=design.hypothetical(reason='Independent headroom audit control',changes={
                'model_assumptions.rf_receive_supply.parameters.headroom_reference_v':2.5})
            row['design_provenance']=variant.provenance()
            row['resolved_configuration']=variant.configure(engine='rf',direction='rx',
                reference_hz=2.426e9,sample_divider=64,pga_gain_db=39).record()
            self.assertTrue(audit(peak)['pga_headroom_design_binding'])
            self.assertFalse(audit(peak)['adc_headroom'])
            row['design_provenance']['design_fingerprint']='invalid'
            self.assertFalse(audit(peak)['pga_headroom_design_binding'])
            self.assertFalse(audit(peak)['adc_headroom'])

    def test_resource_ledger_does_not_treat_allocations_as_measurements(self):
        r=resource_ledger(self.c)
        self.assertFalse(r['closed'])
        self.assertIsNone(r['area']['implemented_total_um2'])
        self.assertIsNone(r['inactive_domain_current_ma'])
        self.assertIsNone(r['storage']['physical_instance_bits'])
        self.assertEqual(r['area']['allocated_um2'],12920000)
        self.assertEqual(r['area']['unallocated_um2'],0)
        self.assertEqual(r['area']['explicit_reserve_um2'],self.c['area_um2']['reserve'])
        changed=copy.deepcopy(self.c)
        changed['area_um2']['reserve']-=1234
        self.assertEqual(resource_ledger(changed)['area']['explicit_reserve_um2'],r['area']['explicit_reserve_um2']-1234)
        self.assertEqual(r['total_allocated_current_ma'],350)
        self.assertEqual(r['terminals']['supply_return'],14)
        self.c['power']['domains'][0]['per_connection_budget_ma']=40
        self.assertEqual(resource_ledger(self.c)['total_allocated_current_ma'],342)
        self.c['transport']['direct_stream']['host_clock_hz']=125000000
        with self.assertRaisesRegex(ValueError,'USB direct-stream clock/encoding'):check(self.c)

    def test_review_evidence_reports_changed_missing_and_unmanifested_sources(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from check_contract import review_evidence_freshness
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';report=root/'report'
            source.write_text('first')
            report.write_text(json.dumps({'case':{'sources_sha256':{
                'source':hashlib.sha256(b'first').hexdigest()}}}))
            closure={'milestone':{'review_evidence':{
                'test':{'file':'report','section':'case'}}}}
            def row():return review_evidence_freshness(root,closure)['areas'][0]
            self.assertEqual(row()['status'],'sources_match')
            source.write_text('changed')
            self.assertEqual(row()['changed_sources'],['source'])
            self.assertEqual(row()['status'],'stale')
            source.unlink()
            self.assertEqual(row()['missing_sources'],['source'])
            report.write_text('{"case": {}}')
            self.assertEqual(row()['status'],'missing_manifest')
            report.write_text('{}')
            self.assertEqual(row()['status'],'missing_section')
            report.unlink()
            self.assertEqual(row()['status'],'missing_report')

    def test_declared_modes(self):
        modes = check(self.c)
        self.assertEqual(modes[0]['used_words_per_direction'], {'d2h': 58, 'h2d': 58})
        self.assertEqual(modes[1]['used_words_per_direction'], {'d2h': 59, 'h2d': 59})

    def test_physical_sites_cannot_be_hidden_by_logical_budget(self):
        r=assembly_ledger(self.c)
        self.assertEqual((r['provider_sites'],r['provider_signal_sites'],r['fixed_supply_return_sites']),(74,56,18))
        self.assertEqual(r['required_signals_plus_fixed_supply_sites'],55)
        self.assertEqual(r['minimum_excess_over_logical_target'],4)
        self.assertEqual(r['spare_signal_sites'],19)
        self.assertFalse(r['closed'])
        self.assertIsNone(r['delivered_board_terminal_count'])
        sites=self.c['assembly_policy']['provider_site_inventory']['ordered_sites_by_side']
        sites['south'].remove('dvss_pads[0].pad')
        with self.assertRaisesRegex(ValueError,'missing fixed provider'):assembly_ledger(self.c)

    def test_signal_map_preserves_supplies_and_pair_adjacency(self):
        mapping=self.c['assembly_policy']['candidate_signal_sites']
        mapping['REF_IN']='dvss_pads[5].pad'
        with self.assertRaisesRegex(ValueError,'fixed supply site'):assembly_ledger(self.c)
        mapping['REF_IN']='inputs[1].pad'
        mapping['REF_IN_N']='inputs[2].pad'
        with self.assertRaisesRegex(ValueError,'reference pair adjacency'):assembly_ledger(self.c)
        mapping['REF_IN_N']='inputs[0].pad'
        mapping['RF_RX_N']='inputs[9].pad'
        with self.assertRaisesRegex(ValueError,'pair adjacency'):assembly_ledger(self.c)
        mapping['RF_RX_N']='inputs[10].pad'
        mapping['HOST_MISO']=mapping['HOST_MOSI']
        with self.assertRaisesRegex(ValueError,'duplicate provider'):assembly_ledger(self.c)

    def test_clock_ownership_and_half_rate_rf_capacity(self):
        rows=operating_clock_ledger(self.c)['configurations']
        self.assertTrue(all(r['d2h_capacity_with_ppm_margin'] and r['h2d_capacity_with_ppm_margin'] and r['d2h_within_host_rate_ceiling'] for r in rows))
        slow=next(r for r in rows if r['configuration']=='rf_direct_lo_2400000000_div64_worddiv16')
        self.assertEqual(slow['fpga_tx_items_per_d2h_word'],[1,4])
        self.assertEqual(slow['d2h_word_hz'],150e6)
        self.assertEqual(slow['d2h_ddr_clock_hz'],75e6)
        direct=[r for r in rows if r['ref_in_role']=='external_lo']
        self.assertEqual(len(direct),8)
        self.assertTrue(all(r['d2h_word_hz']==r['ref_in_hz']/16 for r in direct))
        self.assertEqual(slow['payload_demand_bps'],900e6)
        self.assertAlmostEqual(slow['frame_duration_s'],64/150e6)
        self.assertTrue(slow['retune_changes_conversion_and_d2h'])
        self.assertFalse(slow['sustained_fifo_verified'])
        self.c['transport']['control_words']=40
        overloaded=operating_clock_ledger(self.c)['configurations']
        self.assertTrue(any(not r['d2h_capacity_with_ppm_margin'] for r in overloaded))

    def test_capability_rates_do_not_hide_queue_or_tuning_gaps(self):
        report=milestone_coverage(self.c)
        rows={r['capability']:r['host_service'] for r in report['capabilities']}
        self.assertEqual(set(rows),set(self.c['generic_control_surface']['external_interface_requirements']))
        self.assertTrue(rows['pcie_gen1']['all_listed_points_fit_bulk_capacity_with_ppm'])
        self.assertFalse(rows['pcie_gen1']['all_listed_backlog_bounds_within_planning_allocation'])
        self.assertTrue(rows['pcie_gen1']['selected_snapshot_bounds_within_planning_allocation'])
        self.assertEqual(rows['hdmi_tmds']['chip_instances'],3)
        self.assertEqual(rows['usb2']['roles'],['host','device'])
        self.assertEqual(rows['lower_frequency_rf_stretch']['configurations'],[])
        self.assertEqual(rows['wifi_he20']['per_chip_d2h_ddr_clock_range_hz'],[75e6,78.125e6])
        # A further halving loses wideband bulk capacity; it must be exposed.
        candidate=self.c['generic_configuration_target']['external_lo_sampling_candidate']
        candidate['d2h_word_divider']=32;candidate['d2h_ddr_clock_divider']=64
        changed=milestone_coverage(self.c)
        wifi=next(r for r in changed['capabilities'] if r['capability']=='wifi_he20')
        self.assertFalse(wifi['host_service']['all_listed_points_fit_bulk_capacity_with_ppm'])

    def test_service_bound_prices_gaps_and_rejects_persistent_overload(self):
        args=dict(arrival_item_hz=40e6,item_bits=24,word_hz=156.25e6,
                  frame_words=64,payload_words=59,staging_frames=2,cdc_words=2)
        base=periodic_stream_bound(**args)
        stalled=periodic_stream_bound(**args,extra_service_gap_s=1e-6)
        self.assertTrue(base['rate_stable'])
        self.assertLessEqual(base['backlog_bound_bits'],1024)
        self.assertGreater(stalled['backlog_bound_bits'],1024)
        self.assertEqual(stalled['backlog_bound_bits']-base['backlog_bound_bits'],960)
        overload=periodic_stream_bound(**dict(args,word_hz=50e6))
        self.assertFalse(overload['rate_stable'])
        self.assertIsNone(overload['backlog_bound_bits'])

    def test_hidden_terminal(self):
        self.c['pins'].append({'name':'PADDLE','direction':'power','kind':'ground'})
        with self.assertRaisesRegex(ValueError, 'terminal budget'): check(self.c)

    def test_duplicate_terminal(self):
        self.c['pins'][0] = copy.deepcopy(self.c['pins'][1])
        with self.assertRaisesRegex(ValueError, 'duplicate terminal'): check(self.c)

    def test_wrong_bus_direction(self):
        next(p for p in self.c['pins'] if p['name']=='H2D_D[0]')['direction']='out'
        with self.assertRaisesRegex(ValueError, 'H2D bus'): check(self.c)

    def test_max_radio_and_pcie_do_not_fit(self):
        self.c['modes'][1]['sources'][1]['rate_bps'] = 960000000
        with self.assertRaisesRegex(ValueError, 'overcommit'): check(self.c)

    def test_slow_host_cannot_carry_pcie(self):
        self.c['modes'][1]['profile'] = 'ddr125'
        with self.assertRaisesRegex(ValueError, 'overcommit'): check(self.c)

    def test_directions_have_independent_capacity(self):
        mode = self.c['modes'][1]
        mode['sources'] = [{'id':'wire','directions':['d2h'],'rate_bps':2500000000,'sample_bits':10},
                           {'id':'iq','directions':['h2d'],'rate_bps':2500000000,'sample_bits':16}]
        self.assertEqual(check(self.c)[1]['used_words_per_direction'], {'d2h':52,'h2d':52})

    def test_area_overflow(self):
        self.c['area_um2']['reserve'] += 1
        with self.assertRaisesRegex(ValueError, 'area budget'): check(self.c)

    def test_control_slot_collision(self):
        self.c['transport']['scheduling']['control_slots'] = [0, 0]
        with self.assertRaisesRegex(ValueError, 'control slot'): check(self.c)

    def profile(self, name):
        return next(p for p in self.c['protocol_profiles'] if p['id'] == name)

    def test_usb_cannot_use_input_only_pad(self):
        next(p for p in self.c['pins'] if p['name']=='WIRE_RX_P')['direction']='in'
        with self.assertRaisesRegex(ValueError, 'USB bidirectional'): check(self.c)

    def test_usb_cannot_use_bulk_latency_contract(self):
        self.profile('usb2')['host_service']='framed'
        with self.assertRaisesRegex(ValueError, 'USB response'): check(self.c)

    def test_dp_cannot_silently_add_lanes(self):
        self.profile('displayport_rbr')['lanes']=2
        with self.assertRaisesRegex(ValueError, 'lane allocation'): check(self.c)

    def test_hbr_is_outside_clock_budget(self):
        self.c['physical_services']['serial_target_rates_bps'].append(2700000000)
        with self.assertRaisesRegex(ValueError, 'rate envelope'): check(self.c)

    def test_wifi_cannot_silently_double_bandwidth(self):
        self.profile('wifi_he20')['channel_bandwidth_max_hz']=40000000
        with self.assertRaisesRegex(ValueError, 'bandwidth'): check(self.c)

    def test_rf_cannot_take_wired_pads(self):
        self.profile('lora_24')['pins'][0]='WIRE_RX_P'
        with self.assertRaisesRegex(ValueError, 'RF pad'): check(self.c)

    def test_architecture_is_not_qualification(self):
        self.profile('sata_gen1')['standards_compliant']=True
        with self.assertRaisesRegex(ValueError, 'qualification'): check(self.c)

    def test_profiles_cannot_enable_simultaneous_engines(self):
        self.c['operating_policy']['rf_wired_simultaneous_permitted']=True
        with self.assertRaisesRegex(ValueError, 'exclusive engine'): check(self.c)

if __name__ == '__main__': unittest.main()
