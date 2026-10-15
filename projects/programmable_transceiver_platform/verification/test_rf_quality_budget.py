"""Shared RF allocations and independent budget/admission mathematics.

Changed error/current allocations are explicit accounting fixtures, not legal
hardware configurations. The waveform pre-emphasis comparison retains one design
snapshot and a separately identified hypothetical converter alternative.
"""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from design_definition import load_design
from architecture_fast.rf_quality_budget import evaluate_budget,converter_noise_fraction,air_response_budget,frontend_recovery_budget


TEST_DESIGN_ROLES = {
    'RFQualityTests': ('shared_design', 'Shared error/current allocations and explicitly identified converter alternatives; independent arithmetic and malformed-budget controls.'),
    'RFQualityTests.test_converter_backoff_cost': ('independent_fixture', 'Assigned ENOB/backoff values check converter-noise arithmetic.'),
    'RFQualityTests.test_causal_timing_and_rate_rejection': ('independent_fixture', 'Assigned rates/delays test response-budget arithmetic.'),
    'RFQualityTests.test_frontend_guard_cannot_hide_steady_leakage': ('independent_fixture', 'Assigned leakage and decay constants test recovery bounds.'),
    'RFQualityTests.test_receiver_recovery_uses_air_gap_not_switch_time': ('independent_fixture', 'Independent air-gap, switch and receive-delay arithmetic.'),
}

class RFQualityTests(unittest.TestCase):
    def allocation(self):
        return load_design().architecture['rf_interoperability']['tx_error_allocation']

    def test_selected_allocation_and_correlation_risk(self):
        a=self.allocation()
        self.assertTrue(evaluate_budget(a)['meets_allocation'])
        self.assertFalse(evaluate_budget(a,independent_noise=False)['meets_allocation'])
        a['bounded_residual_fraction']['nonlinearity_including_external_pa']=.03
        self.assertFalse(evaluate_budget(a)['meets_tx_limit'])

    def test_partial_correlation_matches_explicit_covariance_sum(self):
        a=self.allocation();noise=list(a['uncorrelated_rms_fraction'].values())
        r=evaluate_budget(a,noise_correlation=.25)
        variance=sum(x*x for x in noise)+2*.25*sum(noise[i]*noise[j]
            for i in range(len(noise)) for j in range(i+1,len(noise)))
        self.assertAlmostEqual(r['evm_fraction'],variance**.5+sum(a['bounded_residual_fraction'].values()))
        threshold=r['maximum_correlation_for_target']
        self.assertGreater(threshold,0);self.assertLess(threshold,.25)
        self.assertFalse(evaluate_budget(a,noise_correlation=threshold+.001)['meets_allocation'])
        self.assertAlmostEqual(evaluate_budget(a,noise_correlation=1)['evm_fraction'],
            evaluate_budget(a,independent_noise=False)['evm_fraction'])

    def test_converter_backoff_cost(self):
        self.assertLess(converter_noise_fraction(8,6),converter_noise_fraction(8,10))
        self.assertGreater(converter_noise_fraction(8,10),.006)
        self.assertLess(converter_noise_fraction(8,6),.01)

    def test_causal_timing_and_rate_rejection(self):
        a=dict(sample_hz=38.625e6,rx_delay_s=.4e-6,fpga_decision_s=2e-6,
               tx_delay_s=.4e-6,board_settle_s=.5e-6,uncertainty_s=.1e-6,response_gap_s=10e-6)
        r=air_response_budget(**a)
        self.assertTrue(r['admitted'])
        self.assertGreater(r['total_s'],5e-6)
        self.assertFalse(air_response_budget(**{**a,'fpga_decision_s':8e-6})['admitted'])
        self.assertFalse(air_response_budget(**{**a,'d2h_words_hz':80e6})['admitted'])
        self.assertFalse(air_response_budget(**{**a,'board_settle_s':20e-6})['admitted'])

    def test_frontend_guard_cannot_hide_steady_leakage(self):
        case=dict(initial_residual_dbm=-12,steady_residual_dbm=-100,
                  allowed_residual_dbm=-90,recovery_tau_s=50e-9,
                  switch_settle_s=100e-9,available_s=.5e-6)
        self.assertFalse(frontend_recovery_budget(**case)['admitted'])
        self.assertTrue(frontend_recovery_budget(**{**case,'initial_residual_dbm':-30})['admitted'])
        self.assertFalse(frontend_recovery_budget(**{**case,'steady_residual_dbm':-80,'available_s':1.})['admitted'])

    def test_actual_tx_backoff_changes_converter_admission(self):
        from rf_filter_tradeoff import tx_preemphasis_screen
        args=dict(filter_family='rx_all_pole_control',cutoff_hz=12e6,taps=49,
                  coefficient_fraction_bits=12,resampler_span=40,
                  resampler_fraction_bits=14,integrator_ratio=10)
        from unittest.mock import patch
        design=load_design()
        # A supplied snapshot must not be mixed with a later disk reload.
        with patch('rf_filter_tradeoff.load_design',side_effect=AssertionError('Unexpected design reload')):
            low=tx_preemphasis_screen(design=design,amplitude=.08,**args)
        self.assertEqual(low['dac_enob'],design.architecture['model_assumptions']['paired_dac']['parameters']['enob'])
        self.assertEqual(low['design_provenance'],design.provenance())
        self.assertEqual(low['resolved_configuration']['sample_hz'],37.6875e6)
        self.assertEqual(low['result_role'],'simplified_component_diagnostic')
        self.assertGreater(low['native_sine_referenced_backoff_db'],20)
        self.assertTrue(low['crc_ok'])
        self.assertFalse(low['combined_allocation_screen']['meets_tx_limit'])
        candidate=tx_preemphasis_screen(design=design,dac_enob=9.,amplitude=.12,**args)
        self.assertNotEqual(candidate['design_provenance']['design_fingerprint'],design.fingerprint)
        self.assertTrue(candidate['design_provenance']['circuit_experiments'])
        self.assertTrue(candidate['combined_allocation_screen']['converter_meets_allocation'])
        self.assertTrue(candidate['combined_allocation_screen']['meets_allocation'])
        self.assertLess(candidate['native_component_peak'],511/512)
        self.assertFalse(candidate['relative_mask_screen']['qualification'])

    def test_external_source_current_credit_is_explicit_and_local(self):
        from architecture_fast.rf_quality_budget import current_allocation
        a=load_design().architecture
        base=current_allocation(a,'rf_tx')
        primary=current_allocation(a,'rf_tx',branch='external_rf_clock')
        candidate=current_allocation(a,'rf_tx',branch='external_rf_clock',
                                     additional_ma={'txfilter_i':3.,'txfilter_q':3.})
        selected=sum(block['resource_allocation']['current_budget_ma']['rf_tx']
                     for block in a['blocks'].values())
        overrides=a['resource_policy']['branch_current_overrides_ma']['external_rf_clock']
        credit=sum(a['blocks'][name]['resource_allocation']['current_budget_ma']['rf_tx']-value
                   for name,value in overrides.items())
        ceiling=a['resource_policy']['current_ceiling_ma']['rf_tx']
        self.assertAlmostEqual(base['total_ma'],selected)
        self.assertAlmostEqual(primary['total_ma'],selected-credit)
        self.assertAlmostEqual(candidate['total_ma'],selected-credit+6.)
        self.assertAlmostEqual(candidate['margin_ma'],ceiling-(selected-credit+6.))
        self.assertEqual(base['meets_allocation'],selected<=ceiling)
        self.assertEqual(candidate['meets_allocation'],selected-credit+6.<=ceiling)
        self.assertFalse(candidate['physical_qualification'])
        self.assertAlmostEqual(base['by_rail_ma']['pll']-primary['by_rail_ma']['pll'],credit)
        self.assertEqual(base['by_rail_ma']['rf'],primary['by_rail_ma']['rf'])
        self.assertAlmostEqual(candidate['by_rail_ma']['rf']-primary['by_rail_ma']['rf'],6.)
        with self.assertRaises(ValueError):current_allocation(a,'wired',branch='external_rf_clock')
        with self.assertRaises(ValueError):current_allocation(a,'rf_tx',additional_ma={'dac_i':-1.})

    def test_amplifier_current_screen_retains_supplied_design_and_fixture_scope(self):
        from design_definition import DesignDefinition
        from rf_filter_tradeoff import tx_amplifier_current_screen
        from unittest.mock import patch
        base=load_design();architecture=base.architecture
        architecture['rf_interoperability']['external_frontend']['tx_filter_candidate_resource_screen']['per_filter_current_ceiling_ma']=.1
        variant=DesignDefinition.from_documents(base.contract,architecture)
        with patch('rf_filter_tradeoff.load_design',side_effect=AssertionError('Unexpected reload')):
            result=tx_amplifier_current_screen(design=variant)
        self.assertEqual(result['design_provenance'],variant.provenance())
        self.assertEqual(result['result_role'],'simplified_component_requirement_screen')
        self.assertTrue(all(row['candidate_branch_ceiling_ma']==.1 for row in result['rows']))
        self.assertTrue(all(not row['within_candidate_allocation'] for row in result['rows']))
        self.assertEqual(result['diagnostic_assumptions']['temperature_k'],300.15)

    def test_invalid_inputs(self):
        a=self.allocation();a['uncorrelated_rms_fraction']['clock']=float('nan')
        with self.assertRaises(ValueError):evaluate_budget(a)
        with self.assertRaises(ValueError):converter_noise_fraction(8,-1)

    def test_receiver_recovery_uses_air_gap_not_switch_time(self):
        from architecture_fast.rf_quality_budget import receiver_recovery_admission
        args=dict(peer_gap_s=10e-6,tx_tail_s=.5e-6,switch_s=.5e-6,
                  receive_pipeline_s=.15e-6,reserve_s=2e-6)
        result=receiver_recovery_admission(recovery_s=2.454e-6,**args)
        self.assertTrue(result['admissible'])
        self.assertAlmostEqual(result['available_recovery_s'],6.85e-6)
        self.assertFalse(receiver_recovery_admission(recovery_s=7e-6,**args)['admissible'])
