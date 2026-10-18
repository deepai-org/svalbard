"""Independent conservation and enclosure checks for the selected baseline."""
import unittest
import json
import numpy as np
from baseline_envelope import MODE_CURRENT_A, selected_dc_ledger, rail_excursion
from robustness_envelope import shared_board_candidate


from design_definition import load_design


# Explicit intent; declarations alone do not certify downstream parameter ownership.
TEST_DESIGN_ROLES = {
    'CommonEnvelopeMigrationTests.test_periodic_source_mismatch_revokes_receiver_readiness': ('independent_fixture', 'Assigned validated constant-clock fit and subsequent local-voltage phase jump test transactional activation and revocation at DATA validity.'),
    'CommonEnvelopeMigrationTests.test_periodic_learner_observations_commit_with_receiver': ('independent_fixture', 'Voltage-only local observations cannot leak from prediction or grant readiness before periodic acquisition.'),
    'CommonEnvelopeMigrationTests.test_staggered_phase_banks_are_bounded_with_sparse_observations': ('independent_fixture', 'Sparse observed transitions must expire incomplete fits and bound estimator storage.'),
    'CommonEnvelopeMigrationTests.test_staggered_phase_state_is_transactional': ('independent_fixture', 'Overlapping fits use local voltage observations and preserve forecast/commit semantics.'),
    'CommonEnvelopeMigrationTests.test_quadratic_phase_estimate_recovers_endpoint_and_slew': ('independent_fixture', 'Exact irregularly sampled phase polynomial and degenerate geometry establish estimator mathematics.'),
    'CommonEnvelopeMigrationTests.test_quadratic_phase_observer_state_commits_without_edge_oracle': ('independent_fixture', 'Locally sampled voltage drives estimator; unused source labels/root methods cannot enter feedback, and prediction is transactional.'),
    'CommonEnvelopeMigrationTests.test_batched_phase_voltages_match_scalar_channel': ('independent_fixture', 'Batched/scalar equivalence across physical-time channel, equalizer, supply and aperture inputs; same equations and observation endpoints.'),
    'CommonEnvelopeMigrationTests.test_phase_bank_reports_bins_and_rejects_ambiguous_comparators': ('independent_fixture', 'Analytic comparator codes test finite local-slot quantization and ambiguous-pattern rejection.'),
    'CommonEnvelopeMigrationTests.test_phase_bank_feedback_uses_only_local_voltage_samples': ('independent_fixture', 'Same voltage stimulus with contradictory unused source labels verifies sample-only feedback and transactional forecast.'),
    'CommonEnvelopeMigrationTests.test_gap_recovery_window_and_frequency_update_commit_causally': ('independent_fixture', 'Sample-only gap recovery, one-shot frequency boost, window return and elapsed-slew frequency enclosure.'),
    'CommonEnvelopeMigrationTests.test_phase_window_uses_samples_and_preserves_bounded_missing_observations': ('independent_fixture', 'Sampled phase brackets, isolated observation loss, and eventual stale-bound rejection without voltage roots.'),
    'CommonEnvelopeMigrationTests.test_early_late_update_does_not_depend_on_unobserved_gap_history': ('independent_fixture', 'Fixed per-transition binary correction, without an implicit gap-dependent gain scheduler.'),
    'CommonEnvelopeMigrationTests.test_early_late_detector_has_only_three_sample_information': ('independent_fixture', 'Three-sample detector truth table and timestamp-only estimator rejection.'),
    'CommonEnvelopeMigrationTests.test_early_late_feedback_never_queries_voltage_roots_or_claims_phase_magnitude': ('independent_fixture', 'Causal sample-only control and absent magnitude qualification; no physical performance claim.'),
    'CommonEnvelopeMigrationTests.test_slope_predictor_commits_causally_and_prices_gap_motion': ('independent_fixture', 'Assigned CDR slope state checks forecast/commit and conservative gap-motion accounting; not physical qualification.'),
    'ConverterDynamicsTests.test_causal_recharge_extension_preserves_committed_prefix': ('shared_design', 'Shared SAR and differential package; assigned constant supplies and tone isolate numerical causality and charge conservation.'),
    'CommonEnvelopeMigrationTests': ('shared_design', 'Shared environment ownership, propagation and missing-input guards; malformed bindings and prescribed waveforms are explicit controls.'),
    'BaselineBudgetTests': ('independent_fixture', 'Independent passive-network, channel, charge and timing equations with assigned mathematical circuits and stimuli.'),
    'CommonEnvelopeMigrationTests.test_causal_cdr_rejects_counter_without_phase_margin': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_cdr_holdover_includes_frequency_slew_in_admission_and_observation': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_physical_cdr_uses_explicit_loop_and_noise_settings': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_window_frequency_estimator_commits_causal_state_and_tracks_constant_period': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_returning_transition_preserves_incoming_motion_budget': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_timestamp_noise_tail_is_not_a_hard_or_rms_bound': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_holdover_inverse_budget_preserves_units_and_slew': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_aperture_motion_bound_covers_interior_excursions': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_observed_frequency_uncertainty_restricts_holdover_causally': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_regression_frequency_estimator_keeps_bounded_causal_state': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'CommonEnvelopeMigrationTests.test_diagnostic_loading_and_cycle_uncertainty_affect_actual_sar': ('independent_fixture', 'Prescribed primitive CDR/SAR parameters and waveforms test equations or causal state, not selected-chip performance.'),
    'BaselineBudgetTests.test_duplex_wired_clocks_are_independent_and_chunk_invariant': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_selected_differential_clock_routes_both_legs_and_charges_bias_once': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_actual_tx_events_preserve_transport_bits_and_chunking': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_wired_tx_queue_capacity_propagates_from_shared_contract': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_observed_reference_halt_drains_actual_tx_queue': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_wired_shared_rails_preserve_mode_budget_and_clock_ownership': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_adc_activity_cannot_borrow_dac_or_reference_allocations': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_pad_return_uses_the_selected_host_output_load': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_tx_current_margin_matches_dc_resistance_and_rejects_invalid_baseline': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'BaselineBudgetTests.test_differential_reference_load_against_seven_node_solution': ('shared_design', 'Shared configuration or inventory seeds the exercised path; explicit numerical stimuli, topology controls and rejected inputs remain scoped fixtures.'),
    'SelectedRFTests': ('independent_fixture', 'Independent rail FFT, phase, converter and filter equations with explicitly assigned mathematical circuits.'),
    'SelectedRFTests.test_receiver_noise_interventions_preserve_legacy_all_off_control': ('shared_design', 'Reasoned hypothetical PGA snapshot through shared receiver; noise removal is an explicit intervention.'),
    'ConverterDynamicsTests': ('independent_fixture', 'Assigned SAR/reference/load circuits checked by charge conservation, independent ODEs and causal continuation.'),
    'ConverterDynamicsTests.test_native_load_continuation_matches_unbroken_activity_and_rejects_reset_errors': ('shared_design', 'Shared network and differential input parameters with prescribed current trajectory and continuation fault controls.'),
    'WiredIntegrationTests': ('independent_fixture', 'Assigned channel and host publication clocks checked by independent state-space and time equations.'),
    'WiredIntegrationTests.test_internal_usb_return_matches_independent_three_node_mna': ('shared_design', 'Shared USB supply network with explicitly injected switching load checked against independent nodal equations.'),
    'WiredIntegrationTests.test_usb_dc_voltage_matches_independent_pad_and_board_return_reference': ('shared_design', 'Shared FS output resistance and pad network; prescribed rail and external loads checked by independent resistor equations.'),
    'DriverWakeTests': ('independent_fixture', 'Assigned driver and passive network with independent ramp charge and DC limits.'),
    'WiredSupplyObservationTests': ('independent_fixture', 'Prescribed receiver timing, eye and rail fixtures test causal observation bookkeeping.'),
    'HSPadReturnTests': ('independent_fixture', 'Independent primitive pad/return transfer checked against explicit nodal network.'),
    'HSPadReturnTests.test_dc_return_current_is_redirected_not_added_to_budget': ('shared_design', 'Shared USB current allocation and pad parameters checked against independent DC current conservation.'),
    'HostRateTradeoffTests': ('shared_design', 'Shared USB inventory with explicitly recorded historical host-rate interventions and independent latency equations.'),
    'PeriodicClockConsumerTests': ('independent_fixture', 'Prescribed periodic edges and delayed-clock continuation examples.'),
    'PeriodicClockConsumerTests.test_coupled_environment_balances_power_and_rejects_broken_clock': ('shared_design', 'Shared network with explicitly single-ended hypothetical topology and reasoned adverse package scenario.'),
    'RetainedWiredRailTests': ('independent_fixture', 'Prescribed channel and supply waveforms check linear scaling and injection location.'),
    'TurnaroundBudgetTests': ('shared_design', 'Shared turnaround and storage allocation; an explicitly reduced contract snapshot tests insufficient capacity.'),
    'SupplyBlockerRequirementTests': ('independent_fixture', 'Assigned ripple/blocker inverse requirements checked against RC transfer, DC loss and explicit sideband integration.'),
    'IndependentPadPeerTests': ('independent_fixture', 'Independent record decoder and explicit peer-passive isolation examples.'),
    'IndependentPadPeerTests.test_decoding_does_not_hide_bad_termination_or_slow_response': ('shared_design', 'Shared pad snapshot with adverse external peer termination and explicitly legacy framed transport fixture.'),
    'IndependentPadPeerTests.test_usb_lifecycle_requires_explicit_peer_transition': ('shared_design', 'Shared pad snapshot through host/device electrical sequencing; prescribed holds are not USB compliance timing.'),
    'ComparatorDeadlineTests': ('independent_fixture', 'Assigned SAR/comparator regeneration and reference trajectories; continuation and conservation examples.'),
    'PartitionedReturnTests': ('shared_design', 'Shared network seed with explicit counterfactual return topology and current injections, checked against independent circuit equations.'),
    'ReferenceReturnTests': ('independent_fixture', 'Prescribed edge/phasor examples and single-ended input primitive, not differential input qualification.'),
    'ReferenceReturnTests.test_loaded_input_matches_series_thevenin_and_power_balance': ('shared_design', 'Shared network seed with an explicitly hypothetical single-ended input branch checked against Thevenin and power equations.'),
    'DomainRLCNetworkTests': ('independent_fixture', 'Assigned domain RLC topology and unphysical abrupt-edge asymptote checked against independent nodal equations.'),
    'FiniteHostCurrentEdgeTests': ('independent_fixture', 'Prescribed causal current kernel checked against direct charge, centroid and Fourier integration.'),
    'SelectedWiredCompositionTests': ('shared_design', 'Shared configured clock and retained ownership lifecycle; explicit rejection mocks and readiness faults preserve result identity.'),
    'OwnerCurrentGateTests': ('shared_design', 'Shared inventory and rail ownership; independently corrupted current allocation is an explicit accounting fault.'),
    'RXDiscontinuityFaultTests': ('shared_design', 'Shared wired transport and loaded-receiver recovery; synthetic qualification loss and ideal observers are explicit controls.'),
    'RXDiscontinuityFaultTests.test_discard_preserves_live_cdr_and_leaves_future_word_uncommitted': ('independent_fixture', 'Prescribed recovered-word source compared across discard and continuous-consumption schedules.'),
    'WidebandConfigurationTests': ('shared_design', 'Shared legal gain/filter ranges with explicit out-of-range rejection and normalized passband probes; not analog qualification.'),
    'DeliveredIQTests': ('independent_fixture', 'Independent bit-packed signed IQ examples and partial-word accounting.'),
    'SharedRFFrontendTests': ('independent_fixture', 'Assigned gain, noise and linearity primitives; independent scaling and partitioned filter continuity checks.'),
    'SelectedPacketTests': ('shared_design', 'One retained RX/TX snapshot; strong diagnostic packet and explicit aperture/timestamp assumptions isolate timing and underflow.'),
    'RFDirectionGateTests': ('shared_design', 'Shared RF clocks, startup and queue allocation; prescribed direction settling and qualification observations isolate transport gating.'),
    'WiredLifecycleEntryTests': ('shared_design', 'Explicit changed contract snapshot drives startup and queue; ideal clock and missing-edge stimuli isolate lifecycle behavior.'),
    'HostFollowStartupLifecycleTests': ('shared_design', 'Changed shared startup guard must propagate through retained ownership and USB recovery.'),
    'LiveAnalogQualificationTests': ('independent_fixture', 'Assigned startup, observations, bare SAR traces and pad examples isolate monitor ordering and conservation, not current-chip readiness.'),
    'LiveAnalogQualificationTests.test_converter_readiness_uses_both_contract_supply_limits': ('shared_design', 'Shared contract acceptance thresholds are applied to synthetic converter observations; stricter contract is an explicit rejection control.'),
    'LiveAnalogQualificationTests.test_converter_observations_expire_independently_and_gate_chip': ('shared_design', 'Shared contract observation rules with prescribed SAR trace and zero-guard state-machine fixture.'),
    'LiveAnalogQualificationTests.test_reference_consumption_points_distinguish_switching_from_invalid_decision': ('shared_design', 'Shared contract acceptance rules on explicit primitive SAR traces and corrupted observations.'),
    'ConverterDiagnosticLifecycleTests': ('independent_fixture', 'Independent SAR reference-charge and ratiometric examples with prescribed supplies and diagnostic capacitance.'),
    'ConverterDiagnosticLifecycleTests.test_diagnostic_selection_after_stream_binding_cannot_arm_normal_source': ('shared_design', 'Shared RF transport configuration and startup with synthetic source; diagnostic selection must reject incompatible binding.'),
    'ConverterDiagnosticLifecycleTests.test_stopped_selection_uses_retained_sar_and_rejects_stale_epoch': ('shared_design', 'Reasoned hypothetical diagnostic capacitance on shared SAR/comparator and transport; constant supply/reference are explicit fixtures.'),
    'SharedTXOutputTests': ('independent_fixture', 'Independent RF pad, square-law output, spectral and conservation equations with assigned circuits and stimuli.'),
    'SharedTXOutputTests.test_amplitude_requirement_bounds_all_iq_angles_at_supply_endpoints': ('shared_design', 'Shared driver/output and amplitude requirement with resolved TX gain and independent endpoint waveform checks.'),
}


def configured_wired_chip(design, direction):
    """Shared chip seed; test callbacks supply ideal/adverse observations."""
    from baseline_envelope import configured_environment
    from selected_lifecycle import selected_transport_assumptions
    from behavioral import BehavioralChip
    config=design.configure(engine='wire',direction=direction,reference_hz=2.5e9,host_divider=8)
    chip=BehavioralChip(selected_transport_assumptions(configured_environment(config)))
    chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=config.line_rate_bps))
    return chip


class CommonEnvelopeMigrationTests(unittest.TestCase):
    def test_quadratic_phase_estimate_recovers_endpoint_and_slew(self):
        import numpy as np
        from behavioral import quadratic_phase_endpoint
        x=np.array([0,3,7,19,51,102,227,410,512.]);u=x/512
        y=.004*x+.5*1e-7*x*x+.123
        moments=(len(x),sum(u),sum(u*u),sum(u**3),sum(u**4),sum(y),sum(u*y),sum(u*u*y))
        endpoint,slew=quadratic_phase_endpoint(moments,512,512)
        self.assertAlmostEqual(endpoint,.004+512e-7,places=13)
        self.assertAlmostEqual(slew,1e-7,places=15)
        with self.assertRaisesRegex(ValueError,'coverage'):
            quadratic_phase_endpoint((8,0,0,0,0,1,0,0),512,512)

    def test_quadratic_phase_observer_state_commits_without_edge_oracle(self):
        import math
        from behavioral import RecoveredWordSource
        class VoltageOnly(RecoveredWordSource):
            def voltage(self,t):return .2 if math.floor(t/1.0002)%2 else -.2
            def locate_crossing(self,*a):raise AssertionError('Root oracle')
            def crossing(self,*a):raise AssertionError('Source oracle')
        rx=VoltageOnly([0]*5000,2.5e9,.1,100.,detector_model='phase_bank',
            detector_phase_bins=96,detector_noise_rms_s=0.,phase_gain=.08,
            frequency_window_ui=512,frequency_fit='quadratic')
        for i in range(300):
            before=(rx.quadratic_frequency_sums,rx.correction,rx.frequency_slope)
            rx.forecast(i)
            self.assertEqual((rx.quadratic_frequency_sums,rx.correction,rx.frequency_slope),before)
            rx.consume(i)
        self.assertLess(abs(rx.frequency+rx.correction-.0002),50e-6)
        self.assertGreater(rx.detected_edges,2900)
        self.assertGreater(rx.quadratic_frequency_sums[0],1)

    def test_staggered_phase_banks_are_bounded_with_sparse_observations(self):
        from behavioral import RecoveredWordSource
        rx=RecoveredWordSource([0]*5000,2.5e9,.1,100.,detector_model='phase_bank',
            frequency_window_ui=512,frequency_fit='quadratic',frequency_fit_hop_ui=64)
        for edge in range(0,10000,200):
            rx.update_staggered_phase_fit(float(edge),edge+.5)
            self.assertLessEqual(len(rx.quadratic_banks),8)
        self.assertEqual(rx.correction,0.)  # No window has eight observations.

    def test_staggered_phase_state_is_transactional(self):
        import math
        from behavioral import RecoveredWordSource
        class VoltageOnly(RecoveredWordSource):
            def voltage(self,t):return .2 if math.floor(t/1.0002)%2 else -.2
            def locate_crossing(self,*a):raise AssertionError('Root oracle')
            def crossing(self,*a):raise AssertionError('Source oracle')
        rx=VoltageOnly([0]*5000,2.5e9,.1,100.,detector_model='phase_bank',
            detector_phase_bins=96,detector_noise_rms_s=0.,phase_gain=.08,
            frequency_window_ui=512,frequency_fit='quadratic',frequency_fit_hop_ui=64)
        for i in range(300):
            before=(rx.quadratic_banks,rx.next_quadratic_bank_ui,rx.correction)
            rx.forecast(i)
            self.assertEqual((rx.quadratic_banks,rx.next_quadratic_bank_ui,rx.correction),before)
            rx.consume(i)
            self.assertLessEqual(len(rx.quadratic_banks),8)
        self.assertTrue(rx.quadratic_banks)
        self.assertLess(abs(rx.frequency+rx.correction-.0002),50e-6)

    def test_periodic_learner_observations_commit_with_receiver(self):
        import math
        from behavioral import RecoveredWordSource
        class VoltageOnly(RecoveredWordSource):
            def voltage(self,t):return .2 if math.floor(t)%2 else -.2
            def locate_crossing(self,*a):raise AssertionError('Root oracle')
            def crossing(self,*a):raise AssertionError('Source oracle')
        rx=VoltageOnly([0]*4000,2.5e9,.1,100.,detector_model='phase_bank',
            periodic_clock_compute_delay_s=32e-6)
        for i in range(250):
            before=rx.periodic_clock_controller.observations
            rx.forecast(i)
            self.assertEqual(rx.periodic_clock_controller.observations,before)
            rx.consume(i)
        self.assertEqual(len(rx.periodic_clock_controller.observations),1)
        self.assertFalse(rx.timing_qualified)
        self.assertIsNone(rx.first_qualified_bit)

    def test_periodic_source_mismatch_revokes_receiver_readiness(self):
        import math
        from behavioral import RecoveredWordSource
        class VoltageOnly(RecoveredWordSource):
            def voltage(self,t):
                return .2 if math.floor(t+(.2 if self.bit_index>=300 else 0.))%2 else -.2
            def locate_crossing(self,*a):raise AssertionError('Root oracle')
            def crossing(self,*a):raise AssertionError('Source oracle')
        rx=VoltageOnly([0]*2000,2.5e9,.1,0.,detector_model='phase_bank',
            periodic_clock_compute_delay_s=32e-6,detector_noise_rms_s=0.)
        # Explicit prior-acquisition fixture isolates activation and revocation.
        controller=rx.periodic_clock_controller
        controller.fit=dict(origin_edge_ui=0.,origin_cycle=0.,intercept_ui=0.,
            period_ui=83333.,phase_cycles=0.,offset_ppm=0.,depth_ppm=0.,phase_limit_ui=.0625)
        controller.state='processing';controller.ready_after_ui=20.
        observations=[];rx.timing_observer=observations.append
        for i in range(50):
            before=(rx.periodic_clock_controller.state,rx.periodic_clock_controller.invalid_cycle)
            rx.forecast(i)
            self.assertEqual((rx.periodic_clock_controller.state,rx.periodic_clock_controller.invalid_cycle),before)
            rx.consume(i)
        self.assertFalse(any(t['qualified'] for t in observations[:20]))
        self.assertTrue(observations[250]['qualified'])
        invalid=rx.periodic_clock_controller.invalid_cycle
        self.assertGreaterEqual(invalid,300)
        self.assertLess(invalid,305)
        self.assertFalse(any(t['qualified'] for t in observations[invalid:]))
        self.assertEqual(rx.periodic_clock_controller.invalid_reason,'observed_phase_mismatch')
        self.assertEqual(rx.qualification_losses,1)

    def test_batched_phase_voltages_match_scalar_channel(self):
        import numpy as np
        from wired_envelope import physical_receiver
        bits=np.random.default_rng(48).integers(0,2,1000).tolist()
        edges=np.r_[0.,np.cumsum(np.linspace(.999,1.005,len(bits))/2.5e9)]
        q=dict(jitter_rms_s=2e-12,jitter_hz=25e6,noise_rms_v=.01,offset_v=.02,
            delay_tones=[dict(frequency_hz=1.5e8,delay_peak_s=2e-12,delay_phase_rad=.7)],
            rail_dc_v=3.3,rail_tones=[dict(frequency_hz=3e8,clock_rail_voltage_peak_v=.03,voltage_phase_rad=.2)],signal_scale=.9)
        times=np.linspace(-.1,980,1024)
        for source_edges in (None,edges):
            for equalizer in ({},dict(ctle_zero_s=200e-12,ctle_pole_s=96e-12)):
                rx=physical_receiver(bits,2.5e9,.1,100.,1e-10,2.7e-12,dict(q,**equalizer),source_edges_s=source_edges)
                scalar=np.array([rx.voltage(t) for t in times])
                final=rx.sample_observations[rx.bit_index]
                batched=rx.phase_bank_voltages(times)
                np.testing.assert_allclose(batched,scalar,rtol=1e-11,atol=1e-12)
                np.testing.assert_allclose(rx.sample_observations[rx.bit_index],final,rtol=1e-11,atol=1e-12)

    def test_phase_bank_reports_bins_and_rejects_ambiguous_comparators(self):
        from behavioral import sampled_phase_bracket
        import numpy as np
        slots=np.linspace(-.375,.375,25)
        for edge in (-.19,-.001,.017,.21):
            bits=(slots>=edge).astype(int)
            mid,half=sampled_phase_bracket(0,1,bits,slots)
            self.assertLessEqual(abs(mid-edge),half+1e-15)
            self.assertAlmostEqual(half,1/64)
            self.assertEqual(sampled_phase_bracket(1,0,1-bits,slots),(mid,half))
        self.assertIsNone(sampled_phase_bracket(0,1,[0,1,0,1],[-.3,-.1,.1,.3]))
        self.assertIsNone(sampled_phase_bracket(0,1,[0,0,0,0],[-.3,-.1,.1,.3]))
        self.assertIsNone(sampled_phase_bracket(0,0,[0,0,1,1],[-.3,-.1,.1,.3]))
        with self.assertRaises(ValueError):sampled_phase_bracket(0,1,[0,1],[0.,0.])

    def test_phase_bank_feedback_uses_only_local_voltage_samples(self):
        import math
        from behavioral import RecoveredWordSource
        class VoltageOnly(RecoveredWordSource):
            def voltage(self,t):return .2 if math.floor(t)%2 else -.2
            def locate_crossing(self,*args):raise AssertionError('Numerical crossing oracle used')
            def crossing(self,*args):raise AssertionError('Source edge oracle used')
        receivers=[VoltageOnly(bits,2.5e9,.1,100.,detector_model='phase_bank',
            phase_gain=.06,frequency_gain=.0006,frequency_slope_gain=2e-6)
            for bits in ([0,1]*2000,[1]*4000)]
        outputs=[];traces=[]
        for rx in receivers:
            words=[];observed=[];rx.timing_observer=observed.append
            for i in range(200):
                before=(rx.phase,rx.correction,rx.frequency_slope,rx.detected_edges)
                count_before=len(observed)
                rx.forecast(i)
                self.assertEqual(len(observed),count_before)
                with self.assertRaisesRegex(ValueError,'Consume current'):rx.forecast(i)
                self.assertEqual((rx.phase,rx.correction,rx.frequency_slope,rx.detected_edges),before)
                words.append(rx.consume(i))
            outputs.append((words,rx.phase,rx.correction,rx.frequency_slope,rx.detected_edges))
            traces.append(observed)
        self.assertEqual(outputs[0],outputs[1])
        self.assertEqual(traces[0],traces[1])
        self.assertGreater(sum(t['observed_transition_ui'] is not None for t in traces[0]),1900)
        self.assertGreater(outputs[0][-1],1900)

    def test_phase_window_uses_samples_and_preserves_bounded_missing_observations(self):
        from behavioral import RecoveredWordSource
        class WindowProbe(RecoveredWordSource):
            bad_until=301
            def locate_crossing(self,*args):raise AssertionError('Timestamp oracle')
            def voltage(self,t):
                if 300<=self.bit_index<self.bad_until and self.detector_time_ui is not None:
                    sample=self.bit_index+.5+self.phase
                    boundary=(self.detector_time_ui+sample)/2
                    # Independent faults on the two window comparator outputs;
                    # DATA and the central early/late decision are unchanged.
                    if 1e-6<abs(t-boundary)<.2:return -.2
                return super().voltage(t)
        for stop in (301,500,600):
            rx=WindowProbe([0,1]*400,2.5e9,.15,0.,detector_model='early_late',
                detector_window_ui=1/16,phase_gain=1/512,frequency_gain=1/131072,
                detector_noise_rms_s=0.,holdover_residual_ppm=100.,
                aperture_motion_bound_s=lambda elapsed:0.)
            rx.bad_until=stop;observed=[];rx.timing_observer=observed.append
            for i in range(60):rx.forecast(i);rx.consume(i)
            self.assertTrue(observed[299]['qualified'])
            self.assertTrue(observed[300]['qualified'])
            self.assertFalse(observed[300]['phase_magnitude_observed'])
            self.assertTrue(observed[300]['phase_bound_observed'])
            self.assertGreater(observed[300]['holdover_phase_bound_ui'],observed[299]['holdover_phase_bound_ui'])
            if stop==301:
                self.assertTrue(observed[-1]['qualified'])
                self.assertTrue(observed[301]['phase_window_observed'])
                self.assertLess(observed[301]['holdover_phase_bound_ui'],observed[300]['holdover_phase_bound_ui'])
            elif stop==500:
                self.assertFalse(observed[499]['qualified'])
                self.assertTrue(observed[500]['phase_window_observed'])
                self.assertFalse(observed[500]['qualified']) # Fresh evidence cannot erase earlier invalid DATA.
                self.assertTrue(observed[-1]['qualified'])
            else:self.assertFalse(observed[-1]['qualified'])

    def test_gap_recovery_window_and_frequency_update_commit_causally(self):
        from behavioral import RecoveredWordSource
        class SampleOnly(RecoveredWordSource):
            def locate_crossing(self,*args):raise AssertionError('Timestamp oracle')
        bits=[0,1]*50+[0]*70+[1]+[0,1]*100
        rx=SampleOnly(bits,2.5e9,.15,0.,detector_model='early_late',
            detector_window_ui=1/16,detector_wide_window_ui=1/8,detector_widen_after_ui=64,
            phase_gain=1/512,frequency_gain=1/131072,gap_frequency_boost=4.,
            gap_frequency_boost_after_ui=64,detector_noise_rms_s=0.,holdover_ui=512,
            holdover_residual_ppm=100.,aperture_motion_bound_s=lambda elapsed:0.)
        observed=[];rx.timing_observer=observed.append
        for i in range(30):
            state=(rx.detector_window_wide,rx.detector_wide_last_sign,rx.correction)
            rx.forecast(i)
            self.assertEqual(state,(rx.detector_window_wide,rx.detector_wide_last_sign,rx.correction))
            rx.consume(i)
        self.assertEqual([r['bit_index'] for r in observed if r['gap_frequency_boost_applied']],[170])
        self.assertAlmostEqual(abs(observed[170]['next_period_ui']-observed[169]['next_period_ui']),4/131072)
        self.assertEqual(observed[160]['detector_window_used_ui'],1/16)
        self.assertEqual(observed[164]['detector_window_used_ui'],1/8)
        self.assertEqual(observed[170]['detector_window_used_ui'],1/8)
        self.assertEqual(observed[200]['detector_window_used_ui'],1/16)
        elapsed=observed[169]['time_s']-observed[100]['time_s']
        self.assertAlmostEqual(observed[169]['instantaneous_residual_bound_ppm'],100.+330e6*elapsed)
        self.assertEqual(observed[170]['instantaneous_residual_bound_ppm'],100.)
        self.assertTrue(all(not r['phase_magnitude_observed'] for r in observed))

    def test_early_late_update_does_not_depend_on_unobserved_gap_history(self):
        from behavioral import RecoveredWordSource
        receivers=[]
        for gap in (0,17):
            rx=RecoveredWordSource([1,0]*100,2.5e9,.15,0.,detector_model='early_late',
                phase_gain=1/256,frequency_gain=1/65536,detector_noise_rms_s=0.)
            rx.gap=gap
            rx.forecast(0);rx.consume(0);receivers.append(rx)
        self.assertGreater(receivers[0].detected_edges,0)
        self.assertEqual(receivers[0].phase,receivers[1].phase)
        self.assertEqual(receivers[0].correction,receivers[1].correction)

    def test_early_late_detector_has_only_three_sample_information(self):
        from behavioral import early_late_phase_decision,RecoveredWordSource
        expected={(0,0,0):0,(0,0,1):-1,(0,1,0):0,(0,1,1):1,
                  (1,0,0):1,(1,0,1):0,(1,1,0):-1,(1,1,1):0}
        for samples,result in expected.items():
            self.assertEqual(early_late_phase_decision(*samples),result)
        with self.assertRaises(ValueError):early_late_phase_decision(0,2,1)
        with self.assertRaisesRegex(ValueError,'timestamp'):
            RecoveredWordSource([0,1]*100,2.5e9,.1,0.,detector_model='early_late',frequency_window_ui=128)

    def test_early_late_feedback_never_queries_voltage_roots_or_claims_phase_magnitude(self):
        from behavioral import RecoveredWordSource
        class SampleOnly(RecoveredWordSource):
            def locate_crossing(self,*args):
                raise AssertionError('Precise crossing leaked into early/late controller')
        rx=SampleOnly([0,1]*300,2.5e9,.15,0.,detector_model='early_late',
                      phase_gain=1/256,frequency_gain=1e-6,detector_noise_rms_s=0.)
        observed=[];rx.timing_observer=observed.append
        initial=(rx.phase,rx.correction,rx.bit_index)
        rx.forecast(0)
        self.assertEqual((rx.phase,rx.correction,rx.bit_index),initial)
        self.assertEqual(observed,[])
        rx.consume(0)
        for i in range(1,20):rx.forecast(i);rx.consume(i)
        self.assertGreater(rx.detected_edges,100)
        self.assertNotEqual(rx.correction,0.)
        self.assertEqual(len(observed),200)
        self.assertTrue(all(row['detector_model']=='early_late' for row in observed))
        self.assertTrue(all(not row['phase_magnitude_observed'] and not row['qualified'] for row in observed))

    def test_bound_host_sources_require_shared_load_and_current_owners(self):
        from baseline_envelope import configured_environment,partitioned_host_sources,pad_ground_tones
        design=load_design()
        config=design.configure(engine='wire',direction='rx',reference_hz=2.5e9,host_divider=8)
        environment=configured_environment(config)
        for key in ('inventory_current_a','inventory_current_report'):
            broken=dict(environment);del broken[key]
            for solver in (partitioned_host_sources,pad_ground_tones):
                with self.subTest(key=key,solver=solver.__name__), self.assertRaisesRegex(ValueError,key):
                    solver(broken)
        broken=dict(environment,host_spectrum=dict(environment['host_spectrum']))
        del broken['host_spectrum']['output_cap_f']
        for solver in (partitioned_host_sources,pad_ground_tones):
            with self.assertRaisesRegex(ValueError,'output_cap_f'):
                solver(broken)
        self.assertTrue(partitioned_host_sources(environment))
        limited=dict(environment,host_spectrum=dict(environment['host_spectrum'],
            d2h_harmonics=1,h2d_harmonics=1),internal_switching_loads=[])
        expected={limited['host_spectrum'][key]/2 for key in ('d2h_word_hz','h2d_word_hz')}
        self.assertEqual(set(partitioned_host_sources(limited)),expected)
        self.assertEqual(set(pad_ground_tones(limited)),expected)

    def test_d2h_charge_reaches_seed_and_both_host_source_solvers(self):
        import math
        import numpy as np
        from baseline_envelope import configured_environment,partitioned_host_sources,pad_ground_tones
        design=load_design()
        environments=[]
        for charge in (0.,7e-12,14e-12):
            variant=design.hypothetical(reason='Independent output transition-charge sweep',changes={
                'model_assumptions.host_switching.parameters.d2h_internal_charge_c':charge})
            config=variant.configure(engine='wire',direction='rx',reference_hz=2.5e9,host_divider=8)
            environment=configured_environment(config)
            self.assertEqual(environment['host_spectrum']['d2h_internal_charge_c'],charge)
            environments.append(environment)
        sources=[partitioned_host_sources(e) for e in environments]
        grounds=[pad_ground_tones(e) for e in environments]
        word=312.5e6;frequency=word
        # Ten random data outputs plus both clock transitions: six charges/word;
        # the positive-frequency peak phasor is twice the Fourier coefficient.
        expected=12*word*7e-12/(1+2j*math.pi*frequency*.5e-9)
        np.testing.assert_allclose(sources[1][frequency]-sources[0][frequency],
                                  [-expected,0.,expected,0.,0.],atol=1e-16)
        for f in sources[0]:
            np.testing.assert_allclose(sources[2][f]-sources[1][f],
                                      sources[1][f]-sources[0][f],atol=1e-16)
            self.assertAlmostEqual(abs((grounds[2][f]-grounds[1][f])-
                                       (grounds[1][f]-grounds[0][f])),0.,places=13)
        self.assertNotEqual(grounds[0][frequency],grounds[1][frequency])
        self.assertNotEqual(environments[0]['host_spectrum']['tones'],environments[1]['host_spectrum']['tones'])
        broken=dict(environments[1],host_spectrum=dict(environments[1]['host_spectrum']))
        del broken['host_spectrum']['d2h_internal_charge_c']
        for solver in (partitioned_host_sources,pad_ground_tones):
            with self.assertRaisesRegex(ValueError,'d2h_internal_charge_c'):solver(broken)

    def test_selected_entry_uses_current_inventory_and_explicit_overrides(self):
        from baseline_envelope import selected_environment,inventory_environment,P
        design=load_design();architecture=design.architecture;contract=design.contract
        for mode,carrier,word in (('rf',2.4e9,150e6),('wire',2.5e9,312.5e6)):
            actual=selected_environment(contract,mode,carrier,word,design=design)
            expected=inventory_environment(contract,architecture,mode,carrier,word,design=design)
            self.assertEqual(actual['ledger'],expected['ledger'])
            self.assertEqual(actual['converter_parameters'],expected['converter_parameters'])
            self.assertEqual(actual['host_spectrum']['output_cap_f'],6e-12)
        stress=selected_environment(contract,'wire',2.5e9,312.5e6,output_cap_f=10e-12,return_l=2e-9,design=design)
        self.assertEqual(stress['host_spectrum']['output_cap_f'],10e-12)
        self.assertEqual(stress['network']['return_l_h'],2e-9)

    def test_inventory_converter_never_falls_back_to_bare_defaults(self):
        from baseline_envelope import environment_converter_parameters
        from converter_dynamics import parameters_from_inventory,SARParameters
        from dataclasses import asdict
        from pathlib import Path
        architecture=load_design().architecture
        expected=parameters_from_inventory(architecture)
        selected=environment_converter_parameters(dict(inventory_current_report={},converter_parameters=asdict(expected)))
        self.assertEqual(selected,expected)
        self.assertGreater(selected.diagnostic_input_cap_f,SARParameters().diagnostic_input_cap_f)
        self.assertGreater(selected.unmodeled_cycle_uncertainty_s,0.)
        with self.assertRaisesRegex(ValueError,'missing selected converter'):
            environment_converter_parameters(dict(inventory_current_report={}))
        self.assertEqual(environment_converter_parameters({}),SARParameters())
        from copy import deepcopy
        different=deepcopy(architecture)
        different['blocks']['refbuf']['parameters'].update(
            reservoir_f=150e-12,output_r_ohm=70.,source_limit_a=.0007,quiescent_current_a=.0015)
        changed=parameters_from_inventory(different)
        self.assertEqual((changed.reference_cap_f,changed.reference_r_ohm,
                          changed.reference_limit_a,changed.reference_idle_a),
                         (150e-12,70.,.0007,.0015))
        different=deepcopy(architecture)
        for channel in ('adc_i','adc_q'):
            different['blocks'][channel]['parameters']['native_bits']=8
        with self.assertRaisesRegex(ValueError,'native precision'):
            parameters_from_inventory(different)
        different=deepcopy(architecture)
        different['blocks']['adc_q']['parameters']['native_bits']=8
        with self.assertRaisesRegex(ValueError,'matched ADC allocations'):
            parameters_from_inventory(different)

    def test_tx_case_records_inventory_even_when_clock_is_rejected(self):
        from baseline_envelope import P
        from selected_revision_check import rf_chain_case
        from unittest.mock import patch
        design=load_design();architecture=design.architecture;contract=design.contract
        with patch('selected_revision_check.b.reference_payload_environment',return_value=(None,{})):
            result=rf_chain_case(contract,architecture,'tx_nominal',design=design)
        self.assertEqual(result['status'],'clock_rejected')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['design_binding']['inventory_mode'],'rf_tx')
        self.assertEqual(result['design_binding']['converter_parameters']['diagnostic_input_cap_f'],50e-15)

    def test_bound_driver_wake_rejects_missing_or_foreign_clock_parameters(self):
        from selected_rf import driver_wake_response
        from unittest.mock import patch
        environment=dict(design_provenance=load_design().provenance(),
            reference_load_parameters={'differential':{'mismatch':.2}},
            local_supply_delay_sign=-1.,local_supply_sensitivity_ps_per_mv=.025,
            transmitter_parameters={'rfdriver':{'bias_current_a':.028}})
        for key in ('reference_load_parameters','local_supply_delay_sign',
                    'local_supply_sensitivity_ps_per_mv','transmitter_parameters'):
            broken=dict(environment);del broken[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError,key):
                driver_wake_response(broken,released_current_a=.01,wake_start_s=0.)
        with self.assertRaisesRegex(ValueError,'conflicts'):
            driver_wake_response(environment,released_current_a=.01,wake_start_s=0.,
                                 reference_input={'differential':{'mismatch':0.}})

    def test_bound_feedback_rejects_missing_clock_response_parameters(self):
        from baseline_envelope import reference_feedback_response
        from unittest.mock import patch
        environment=dict(design_provenance=load_design().provenance(),network=object(),
            periodic_clock={},reference_load_parameters={'differential':{}},
            local_supply_delay_sign=-1.,local_supply_sensitivity_ps_per_mv=.025)
        for key in ('reference_load_parameters','local_supply_delay_sign',
                    'local_supply_sensitivity_ps_per_mv'):
            broken=dict(environment);del broken[key]
            with self.subTest(key=key), patch('baseline_envelope.load_response') as solver:
                with self.assertRaisesRegex(ValueError,key):
                    reference_feedback_response({'reference_limit_a':.001},broken)
                solver.assert_not_called()

    def test_shared_pga_response_changes_controller_dynamics(self):
        from ble_packet import receiver_pga_response
        from converter_dynamics import ObservedGain
        design=load_design().hypothetical(reason='Check response propagation',changes={
            'blocks.pga_i.parameters.gain_response_tau_s':1e-6,
            'blocks.pga_q.parameters.gain_response_tau_s':1e-6})
        environment=dict(design_provenance=design.provenance(),receiver_parameters={
            name:design.architecture['blocks'][name]['parameters'] for name in ('pga_i','pga_q')})
        tau=receiver_pga_response(environment)
        self.assertEqual(tau,1e-6)
        gain=ObservedGain(sample_hz=1e6,command_latency_s=0.,acquisition_s=5e-9,
            headroom_start=np.ones(2),headroom_end=np.ones(2),initial_gain_db=0.,
            gain_response_tau_s=tau)
        gain.advance(0.)
        gain.target_db=20.
        # Independent first-order step solution, one time constant after change.
        self.assertAlmostEqual(gain.advance(1e-6),10.-9.*np.exp(-1.))
        self.assertEqual(gain.report()['gain_response_tau_s'],tau)
        from ble_packet import bounded_gain_conversion
        _,report=bounded_gain_conversion(np.zeros(2),np.zeros(2),fs=1e6,
            command_latency_s=0.,initial_gain_db=0.,gain_response_tau_s=tau)
        expected=1.+(10**(6/20)-1.)*(1.-np.exp(-1.))
        self.assertAlmostEqual(report['gain_db'][1],20*np.log10(expected))
        self.assertEqual(report['gain_response_tau_s'],tau)
        del environment['receiver_parameters']['pga_i']['gain_response_tau_s']
        with self.assertRaises(KeyError):receiver_pga_response(environment)
        with self.assertRaises(ValueError):
            receiver_pga_response(dict(design_provenance=design.provenance()))

    def test_simplified_pga_commands_remain_in_inventory(self):
        from ble_packet import bounded_gain_conversion
        design=load_design()
        codes=tuple(design.architecture['blocks']['pga_i']['parameters']['gain_db'])
        _,report=bounded_gain_conversion(np.full(30,.023),np.zeros(30),fs=1e6,
            command_latency_s=0.,initial_gain_db=-6.,maximum_gain_db=max(codes),
            gain_codes_db=codes,gain_response_tau_s=1e-6)
        self.assertTrue(report['commanded_gain_db'])
        self.assertTrue(all(value in codes for value in report['commanded_gain_db']))
        self.assertEqual(report['commanded_gain_db'][0],0.)
        self.assertEqual(report['gain_codes_db'],codes)
        with self.assertRaisesRegex(ValueError,'PGA codes'):
            bounded_gain_conversion(np.zeros(2),np.zeros(2),initial_gain_db=40.,
                maximum_gain_db=max(codes),gain_codes_db=codes)

    def test_packet_pga_uses_only_inventory_gain_codes(self):
        from converter_dynamics import ObservedGain
        design=load_design()
        lanes=design.architecture['blocks']
        codes=tuple(sorted(set(lanes['pga_i']['parameters']['gain_db']) &
                           set(lanes['pga_q']['parameters']['gain_db'])))
        # Synthetic observation timing and unity headroom isolate gain control.
        options=dict(sample_hz=1e6,command_latency_s=1e-6,acquisition_s=5e-9,
            headroom_start=np.ones(8),headroom_end=np.ones(8),
            maximum_gain_db=max(codes),gain_codes_db=codes)
        gain=ObservedGain(initial_gain_db=39.,**options)
        gain.observe(0,0j,1e-6)
        self.assertEqual(gain.pending,(2e-6,42))
        self.assertEqual(gain.target_db,39.)
        gain.advance(3e-6)
        gain.observe(1,1+1j,3e-6)
        self.assertEqual(gain.pending,(4e-6,36))
        self.assertTrue(all(row['target_gain_db'] in codes for row in gain.commands))
        with self.assertRaisesRegex(ValueError,'PGA codes'):
            ObservedGain(initial_gain_db=40.,**options)

    def test_prepared_supply_samplers_preserve_tones_and_feedback(self):
        from selected_rf import prepared_supply_functions,rail_at,reference_at
        times=np.linspace(0,2e-6,1000)
        columns=np.column_stack((.01*np.sin(times*1e7),.001*np.cos(times*1e7)))
        env=dict(ledger={'local_payload_clock_core_rail_v':3.},
            host_spectrum={'tones':[dict(frequency_hz=312.5e6,clock_rail_voltage_peak_v=.04,voltage_phase_rad=.3)]},
            reference_fraction_tones=[(312.5e6,.003,.4)],
            local_load_response=dict(times_s=times,rail_v=columns[:,0],reference_fraction=columns[:,1],
                background={'rail_v':.001,'reference_fraction':.002}))
        rail,ref=prepared_supply_functions(env)
        for query in (np.array([-1e-9]),np.array([.37e-6]),np.array([3e-6]),times,times[:12].reshape(3,4)):
            np.testing.assert_allclose(rail(query),rail_at(env,query),rtol=0,atol=1e-15)
            np.testing.assert_allclose(ref(query),reference_at(env,query),rtol=0,atol=1e-15)
        env['reference_fraction_tones']=np.array(env['reference_fraction_tones'])
        response=env['local_load_response']
        for key in ('rail_v','reference_fraction'):response[key]=response[key].copy()
        query=np.array([.37e-6,.65e-6])
        expected_rail=rail_at(env,query);expected_reference=reference_at(env,query)
        rail,ref=prepared_supply_functions(env)
        response['times_s'][:]*=2
        response['rail_v'][:]=.5
        response['reference_fraction'][:]=.2
        env['reference_fraction_tones'][:,1]=.9
        np.testing.assert_allclose(rail(query),expected_rail,rtol=0,atol=1e-15)
        np.testing.assert_allclose(ref(query),expected_reference,rtol=0,atol=1e-15)

        # A design-bound reference is an absolute voltage. The imposed tone
        # and recharge response are fractional stimuli, independent of target.
        from baseline_envelope import configured_environment
        design=load_design().hypothetical(reason='Reference target propagation check',
            changes={'blocks.refbuf.parameters.target_v':.9})
        bound=configured_environment(design.configure(engine='rf',direction='rx',
            reference_hz=2.4e9,sample_divider=64,pga_gain_db=39))
        bound['reference_fraction_tones']=[(1e6,.02,.3)]
        bound['local_load_response']=dict(times_s=np.array([0.,1e-6]),
            reference_fraction=np.array([.01,.03]),rail_v=np.zeros(2),
            background={'reference_fraction':-.01,'rail_v':0.})
        query=np.array([-1e-7,.25e-6,.75e-6,1.1e-6])
        fractional_feedback=np.array([-.01,.015,.025,-.01])
        expected=.9*(1+.02*np.cos(2*np.pi*1e6*query+.3)+fractional_feedback)
        np.testing.assert_allclose(reference_at(bound,query),expected,rtol=0,atol=1e-15)
        _,prepared=prepared_supply_functions(bound)
        np.testing.assert_allclose(prepared(query),expected,rtol=0,atol=1e-15)
        from selected_rf import reference_scale_at
        np.testing.assert_allclose(reference_scale_at(bound,query),expected/.9,rtol=0,atol=1e-15)
        for invalid in (None,0.,-1.,True,float('nan')):
            from design_definition import DesignDefinition
            architecture=design.architecture
            if invalid is None:del architecture['blocks']['refbuf']['parameters']['target_v']
            else:architecture['blocks']['refbuf']['parameters']['target_v']=invalid
            with self.assertRaises(ValueError):
                DesignDefinition.from_documents(design.contract,architecture)
            broken=dict(bound,reference_supply_parameters=dict(bound['reference_supply_parameters']))
            if invalid is None:del broken['reference_supply_parameters']['target_v']
            else:broken['reference_supply_parameters']['target_v']=invalid
            for evaluate in (lambda:reference_at(broken,query),
                             lambda:prepared_supply_functions(broken)):
                with self.assertRaises(ValueError):evaluate()
        bound['reference_supply_parameters']['target_v']=.8
        np.testing.assert_allclose(prepared(query),expected,rtol=0,atol=1e-15)

    def test_causal_cdr_rejects_counter_without_phase_margin(self):
        from behavioral import RecoveredWordSource
        receiver=RecoveredWordSource([0,1]*100,2.5e9,0.,100.,holdover_ui=512)
        self.assertEqual(receiver.holdover_ui,512)
        self.assertAlmostEqual(receiver.frequency_correction_limit,.007)
        with self.assertRaisesRegex(ValueError,'phase-error budget'):
            RecoveredWordSource([0,1]*100,2.5e9,0.,100.,holdover_ui=2000)

    def test_cdr_holdover_includes_frequency_slew_in_admission_and_observation(self):
        from behavioral import RecoveredWordSource
        from timing_services import cdr_holdover_error
        # A static-frequency budget admits this counter, but an SSC slope does not.
        RecoveredWordSource([],2.5e9,0.,0.,holdover_ui=1024,holdover_frequency_slew_ppm_s=0.)
        with self.assertRaisesRegex(ValueError,'phase-error budget'):
            RecoveredWordSource([],2.5e9,0.,0.,holdover_ui=1024)
        receiver=RecoveredWordSource([0,1]*200+[0]*80,2.5e9,0.,0.)
        observations=[];receiver.timing_observer=observations.append
        for i in range(47):receiver.forecast(i);receiver.consume(i)
        last_error=None
        for row in observations:
            if row['detector_history_peak_ui'] is None:continue
            if row['transition']:last_error=row['holdover_phase_bound_ui']-.0625
            if last_error is not None:
                independent=cdr_holdover_error(line_hz=2.5e9,run_ui=row['gap_ui'],
                    initial_ui=last_error,other_ui=.0625)['error_ui']
                self.assertAlmostEqual(row['holdover_phase_bound_ui'],independent)
            # Single-edge history is not exposed; compare the slew contribution
            # directly with the independent integrated frequency-ramp budget.
            gap=row['gap_ui']
            expected=cdr_holdover_error(line_hz=2.5e9,run_ui=gap,
                residual_ppm=0.,initial_ui=0.,other_ui=0.)['error_ui']
            self.assertAlmostEqual(receiver.holdover_slew_ui_per_gap_squared*gap**2,expected)
            self.assertEqual(row['declared_holdover_frequency_slew_ppm_s'],330e6)
        self.assertTrue(observations)

    def test_physical_cdr_uses_explicit_loop_and_noise_settings(self):
        from wired_envelope import physical_receiver
        options=dict(jitter_rms_s=0.,jitter_hz=1e6,noise_rms_v=0.,offset_v=0.,
            phase_gain=.08,frequency_gain=.002,detector_noise_rms_s=1e-12,
            holdover_frequency_slew_ppm_s=300e6)
        rx=physical_receiver([0,1]*100,2.5e9,0.,0.,100e-12,2.7e-12,options)
        self.assertEqual((rx.phase_gain,rx.frequency_gain,rx.detector_noise_rms_s,
                          rx.holdover_frequency_slew_ppm_s),(.08,.002,1e-12,300e6))
        for key,value in (('phase_gain',0.),('frequency_gain',float('nan')),
                          ('detector_noise_rms_s',-1e-12)):
            with self.assertRaises(ValueError):
                physical_receiver([0,1]*100,2.5e9,0.,0.,100e-12,2.7e-12,
                                  dict(options,**{key:value}))

    def test_slope_predictor_commits_causally_and_prices_gap_motion(self):
        from behavioral import RecoveredWordSource
        for slope in (-1e-7,1e-7):
            rx=RecoveredWordSource([0]*100,2.5e9,0.,0.,frequency_slope_gain=2e-7)
            rx.frequency_slope=slope;rx.edge_errors.extend([.01]*64)
            rx.timing_qualified=True;observed=[];rx.timing_observer=observed.append
            rx.forecast(0)
            self.assertEqual(rx.correction,0.)
            self.assertEqual(observed,[])
            rx.consume(0)
            self.assertAlmostEqual(rx.correction,10*slope,places=15)
            self.assertEqual(observed[-1]['gap_ui'],10)
            expected=.01+.0625+10*50e-6+(.5*330e6*1e-6/2.5e9+.5*abs(slope))*100
            self.assertAlmostEqual(observed[-1]['holdover_phase_bound_ui'],expected,places=14)
        with self.assertRaises(ValueError):
            RecoveredWordSource([0]*100,2.5e9,0.,0.,frequency_slope_gain=2e-7,frequency_window_ui=256)

    def test_window_frequency_estimator_commits_causal_state_and_tracks_constant_period(self):
        from behavioral import RecoveredWordSource
        rx=RecoveredWordSource([0,1]*1200,2.5e9,.35,100.,phase_gain=.08,
            frequency_window_ui=256,detector_noise_rms_s=0.)
        before=(rx.frequency_anchor_ui,rx.frequency_previous_edge_ui,rx.frequency_elapsed_ui,rx.correction)
        rx.forecast(0)
        self.assertEqual(before,(rx.frequency_anchor_ui,rx.frequency_previous_edge_ui,
                                 rx.frequency_elapsed_ui,rx.correction))
        rx.consume(0)
        self.assertIsNotNone(rx.frequency_anchor_ui)
        for i in range(1,200):rx.forecast(i);rx.consume(i)
        self.assertAlmostEqual(rx.correction,-100e-6,places=7)
        self.assertLess(rx.frequency_elapsed_ui,256)
        self.assertTrue(rx.timing_qualified)

    def test_usb_uses_its_inventory_in_the_common_pad_supply(self):
        from pathlib import Path
        from selected_revision_check import usb_inventory_supply
        from rf_quality_budget import current_allocation
        from baseline_envelope import inventory_environment
        p=Path(__file__).resolve().parents[1]
        design=load_design();contract=design.contract;architecture=design.architecture
        result=usb_inventory_supply(contract,architecture,design=design)
        allocated=current_allocation(architecture,'usb')
        ledger=result['ledger']
        self.assertEqual(result['inventory'],allocated)
        self.assertAlmostEqual(sum(ledger['owner_current_a'].values()),allocated['total_ma']/1000)
        self.assertAlmostEqual(ledger['total_chip_supply_current_a'],.2522)
        self.assertLess(abs(ledger['power_balance_residual_w']),1e-12)
        self.assertNotEqual(allocated['total_ma'],current_allocation(architecture,'wired')['total_ma'])
        for mode in ('rf_rx','rf_tx'):
            environment=inventory_environment(contract,architecture,'rf',2.4e9,150e6,inventory_mode=mode,design=design)
            expected=current_allocation(architecture,mode,branch='external_rf_clock')
            self.assertEqual(environment['inventory_current_report'],expected)
            self.assertEqual(environment['converter_parameters']['diagnostic_input_cap_f'],50e-15)
            self.assertEqual(environment['converter_parameters']['unmodeled_cycle_uncertainty_s'],.2e-9)
            self.assertAlmostEqual(environment['ledger']['total_chip_supply_current_a'],expected['total_ma']/1000)
            self.assertLess(abs(environment['ledger']['power_balance_residual_w']),1e-12)
        with self.assertRaises(ValueError):
            inventory_environment(contract,architecture,'rf',2.4e9,150e6,inventory_mode='usb')

    def test_returning_transition_preserves_incoming_motion_budget(self):
        from behavioral import RecoveredWordSource
        bits=[0,1]*300+[0]*30+[0,1]*300
        rx=RecoveredWordSource(bits,2.5e9,.1,0.,detector_noise_rms_s=0.,
            aperture_motion_bound_s=lambda dt:0. if dt<5/2.5e9 else .3/2.5e9)
        trace=[];rx.timing_observer=trace.append
        for i in range(len(bits)//10):rx.forecast(i);rx.consume(i)
        returning=[t for t in trace if 620<t['bit_index']<635 and t['transition']]
        self.assertTrue(returning)
        self.assertFalse(returning[0]['qualified'])
        self.assertTrue(any(t['holdover_phase_bound_ui']>=.25 for t in trace if 600<t['bit_index']<635))
        self.assertTrue(rx.timing_qualified)

    def test_timestamp_noise_tail_is_not_a_hard_or_rms_bound(self):
        from wired_envelope import timestamp_tail_budget
        args=dict(bound_s=25e-12,deterministic_s=10e-12,tail_probability=1e-12)
        failed=timestamp_tail_budget(**args,noise_rms_s=5e-12)
        self.assertFalse(failed['admitted'])
        self.assertAlmostEqual(failed['modeled_tail_probability'],.00269979606326019)
        target=timestamp_tail_budget(**args,noise_rms_s=2e-12)
        self.assertTrue(target['admitted'])
        self.assertLess(target['maximum_noise_rms_s'],2.11e-12)
        self.assertGreater(target['maximum_noise_rms_s'],2.10e-12)
        self.assertFalse(timestamp_tail_budget(**dict(args,deterministic_s=26e-12),noise_rms_s=0.)['admitted'])

    def test_holdover_inverse_budget_preserves_units_and_slew(self):
        from wired_envelope import holdover_phase_budget
        args=dict(rate=2.5e9,gap_ui=100,initial_phase_ui=.05,timestamp_bound_s=20e-12,
            residual_ppm=100,slew_ppm_s=0.,delay_tones=[])
        r=holdover_phase_budget(**args)
        self.assertAlmostEqual(r['total_ui'],.11)
        self.assertAlmostEqual(r['residual_ceiling_ppm'],1500.)
        self.assertTrue(r['admitted'])
        stressed=holdover_phase_budget(**dict(args,slew_ppm_s=1e12))
        self.assertFalse(stressed['admitted'])
        self.assertLess(stressed['residual_ceiling_ppm'],0.)
        with self.assertRaises(ValueError):holdover_phase_budget(**dict(args,rate=0.))

    def test_aperture_motion_bound_covers_interior_excursions(self):
        from wired_envelope import aperture_motion_bound
        tones=[dict(frequency_hz=100e6,delay_peak_s=10e-12)]
        self.assertEqual(aperture_motion_bound(tones,0.),0.)
        # Endpoint displacement is zero after a whole cycle, but the
        # interior half-cycle excursion must remain in the bound.
        self.assertAlmostEqual(aperture_motion_bound(tones,10e-9)/1e-12,20.)
        for duration in (1e-12,1e-9,5e-9,10e-9):
            phases=np.linspace(0,2*np.pi,101)
            intervals=np.linspace(0,duration,101)
            movement=10e-12*np.abs(np.sin(phases[:,None]+2*np.pi*100e6*intervals)-np.sin(phases[:,None]))
            self.assertLessEqual(movement.max(),aperture_motion_bound(tones,duration)+1e-25)
        with self.assertRaises(ValueError):aperture_motion_bound(tones,-1.)

    def test_observed_frequency_uncertainty_restricts_holdover_causally(self):
        from behavioral import RecoveredWordSource
        bits=[0,1]*500+[0]*120+[0,1]*500
        traces=[]
        for bound in (0.,50e-12):
            rx=RecoveredWordSource(bits,2.5e9,.35,100.,phase_gain=.08,
                frequency_window_ui=128,frequency_fit='least_squares',
                detector_noise_rms_s=0.,edge_time_bound_s=bound,holdover_ui=512)
            trace=[];rx.timing_observer=trace.append
            for i in range(len(bits)//10):
                previous=(rx.observed_frequency_bound_ppm,rx.frequency_bound_at_ui)
                rx.forecast(i)
                self.assertEqual(previous,(rx.observed_frequency_bound_ppm,rx.frequency_bound_at_ui))
                rx.consume(i)
            self.assertTrue(rx.timing_qualified)
            self.assertTrue(all(t['effective_holdover_residual_ppm']>=50 for t in trace))
            self.assertTrue(all(t['edge_phase_uncertainty_ui']==max(.0625,bound*2.5e9) for t in trace))
            self.assertTrue(all(t['holdover_phase_bound_ui']>=t['edge_phase_uncertainty_ui'] for t in trace))
            traces.append(trace)
        narrow,wide=traces
        self.assertTrue(any(a['qualified'] and not b['qualified']
            for a,b in zip(narrow,wide) if a['gap_ui']>10))
        self.assertTrue(all(t['holdover_phase_bound_ui']<.25
            for t in wide if t['qualified']))
        with self.assertRaises(ValueError):
            RecoveredWordSource(bits,2.5e9,0.,0.,edge_time_bound_s=1e-12)

    def test_regression_frequency_estimator_keeps_bounded_causal_state(self):
        from behavioral import RecoveredWordSource
        rx=RecoveredWordSource([0,1]*1200,2.5e9,.35,100.,phase_gain=.08,
            frequency_window_ui=128,frequency_fit='least_squares',detector_noise_rms_s=0.)
        before=rx.frequency_sums
        rx.forecast(0)
        self.assertEqual(rx.frequency_sums,before)
        rx.consume(0)
        self.assertGreater(rx.frequency_sums[0],1)
        for i in range(1,200):rx.forecast(i);rx.consume(i)
        self.assertEqual(len(rx.frequency_sums),5)
        self.assertLessEqual(rx.frequency_sums[0],129)
        self.assertAlmostEqual(rx.correction,-100e-6,places=7)
        self.assertTrue(rx.timing_qualified)

    def test_inventory_current_survives_clock_ledger_reduction(self):
        import baseline_envelope as b
        design=load_design()
        allocation=design.architecture['blocks']['rxfilter_i']['resource_allocation']['current_budget_ma']['rf_rx']
        # Explicit allocation variant, not a fabricated device-parameter corner.
        from design_definition import DesignDefinition
        architecture=design.architecture
        architecture['blocks']['rxfilter_i']['resource_allocation']['current_budget_ma']['rf_rx']=allocation+1.
        variant=DesignDefinition.from_documents(design.contract,architecture)
        for mode,word in (('rf',156.25e6),('wire',312.5e6)):
            totals=[]
            for snapshot in (design,variant):
                e=b.inventory_environment(snapshot.contract,snapshot.architecture,mode,2.5e9,word,design=snapshot)
                self.assertGreater(e['host_spectrum']['output_cap_f'],0.)
                ledger=b.partitioned_dc_ledger(e,dict(link_r_ohm=1e-5))
                total=ledger['total_chip_supply_current_a'];totals.append(total)
                self.assertAlmostEqual(total,e['inventory_current_report']['total_ma']/1000)
                self.assertLess(abs(ledger['power_balance_residual_w']),1e-12)
            self.assertAlmostEqual(totals[1]-totals[0],.001 if mode=='rf' else 0.)

    def test_diagnostic_loading_and_cycle_uncertainty_affect_actual_sar(self):
        from dataclasses import replace
        from converter_dynamics import SARParameters,paired_sar
        p=SARParameters();t=(np.arange(8)+1)*25.6e-9
        z=np.full(8,.6+.2j);start=np.zeros(8,complex)
        forcing=(lambda t:np.ones_like(t),lambda t:np.full_like(t,3.3))
        base,_,_=paired_sar(z,start,t,*forcing,parameters=p,noise=False)
        loaded,_,_=paired_sar(z,start,t,*forcing,
            parameters=replace(p,diagnostic_input_cap_f=2e-12,
                               diagnostic_series_resistance_ohm=2000.),noise=False)
        self.assertGreater(float(np.max(abs(base-loaded))),10)
        with self.assertRaisesRegex(ValueError,'schedule does not fit'):
            paired_sar(z,start,t,*forcing,
                       parameters=replace(p,unmodeled_cycle_uncertainty_s=1e-9),noise=False)


class FiniteHostCurrentEdgeTests(unittest.TestCase):
    def test_charge_centroid_and_spectrum_match_causal_kernel(self):
        from robustness_envelope import finite_current_edge_factor
        edge=100e-12;t=np.linspace(0,2*edge,40001)
        kernel=np.maximum(0,1-abs(t-edge)/edge)/edge
        self.assertAlmostEqual(float(np.trapezoid(kernel,t)),1.,places=12)
        self.assertAlmostEqual(float(np.trapezoid(t*kernel,t))/edge,1.,places=12)
        self.assertEqual(finite_current_edge_factor(0.,edge),1.+0j)
        for f in (75e6,1e9,3.7e9):
            direct=np.trapezoid(kernel*np.exp(-2j*np.pi*f*t),t)
            self.assertLess(abs(direct-finite_current_edge_factor(f,edge)),1e-8)

    def test_all_host_ports_receive_same_charge_preserving_filter(self):
        from robustness_envelope import finite_current_edge_factor,host_harmonic_current,h2d_current_ports
        for n in (1,2,13,64):
            f=n*156.25e6;edge=100e-12;factor=finite_current_edge_factor(f,edge)
            self.assertAlmostEqual(host_harmonic_current(f,312.5e6,n,current_edge_s=edge),
                host_harmonic_current(f,312.5e6,n)*factor)
            old=h2d_current_ports(f,312.5e6,n,alternating=True)
            new=h2d_current_ports(f,312.5e6,n,alternating=True,current_edge_s=edge)
            for port in old:self.assertAlmostEqual(new[port],old[port]*factor)


class SelectedWiredCompositionTests(unittest.TestCase):
    def test_wired_probe_uses_differential_clock_and_rejects_before_peer(self):
        from unittest.mock import patch
        import wired_lock_probe as w
        design=load_design();c=design.contract
        with patch.object(w.b,'load_design',side_effect=AssertionError('Unexpected design reload')), \
             patch.object(w.b,'reference_payload_environment',return_value=(None,{'status':'rejected'})) as selected, \
             patch.object(w.b,'single_ended_reference_payload_environment') as old, \
             patch.object(w,'peer_for_environment') as peer:
            with self.assertRaisesRegex(ValueError,'Reference clock rejected'):
                w.environment_for(c,.5,0,design=design)
        selected.assert_called_once();old.assert_not_called();peer.assert_not_called()

    def test_feed_probe_records_rejection_without_receiver_execution(self):
        from unittest.mock import patch
        import feed_failure_probe as f
        with patch.object(f.b,'reference_payload_environment',return_value=(None,{'status':'rejected'})), \
             patch.object(f,'peer_for_environment') as peer, patch.object(f.b,'write_evidence') as write:
            f.main()
        peer.assert_not_called()
        report=write.call_args.args[1]
        self.assertEqual(len(report['cases']),4)
        self.assertEqual(len(report['sensitivity_controls']),3)
        self.assertTrue(all(row['status']=='clock_rejected'
                            for row in report['cases']+report['sensitivity_controls']))
        baseline=load_design()
        for row in report['cases']:
            context=row['clock']
            self.assertEqual(context['resolved_configuration']['line_rate_bps'],2.5e9)
            provenance=context['design_provenance']
            if row['local_feed_resistance_ohm']==2.:
                self.assertEqual(provenance,baseline.provenance())
            else:
                self.assertNotEqual(provenance['design_fingerprint'],baseline.fingerprint)
                self.assertTrue(provenance['circuit_experiments'])
        for row in report['sensitivity_controls']:
            self.assertEqual(row['clock']['probe_assumptions']['sensitivity_ps_per_mv'],
                             row['sensitivity_ps_per_mv'])

    def test_warm_turnaround_requires_independent_readiness_observation(self):
        from selected_lifecycle import ownership_load_trace
        from baseline_envelope import P
        design=load_design()
        contract=design.contract
        result=ownership_load_trace(contract,turnaround=True,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(set(result['resolved_configurations']),{'rf_rx','rf_tx','wired'})
        self.assertEqual(result['unresolved_configurations'],[])
        self.assertTrue(result['lifecycle_stimuli']['turnaround'])
        self.assertEqual(result['pga_nominal_peak_limit_v'],
            design.architecture['blocks']['pga_i']['parameters']['differential_peak_limit_v'])
        self.assertEqual(result['status'],'completed_scoped_lifecycle')
        self.assertEqual(len(result['stages']),7)
        self.assertTrue(result['independent_analog_observations'])
        self.assertLess(abs(result['reference_charge_accounting']['balance_residual_c']),1e-22)
        missing=ownership_load_trace(contract,turnaround=True,independent_analog_observations=False,design=design)
        self.assertEqual(missing['status'],'rejected_by_analog_qualification')
        self.assertAlmostEqual(missing['analog_observation_age_at_fault_s'],200e-9,places=15)

    def test_selected_ctle_has_no_extra_lock_loss_in_joined_encoded_case(self):
        from selected_lifecycle import ownership_load_trace
        from baseline_envelope import P
        from unittest.mock import patch
        design=load_design();contract=design.contract
        with patch('baseline_envelope.load_design',side_effect=AssertionError('Unexpected design reload')):
            result=ownership_load_trace(contract,wired_cdr=True,wired_encoded=True,wired_equalized=True,design=design)
        audit=result['stages'][2]['wired_analog_cdr']
        self.assertEqual(result['status'],'completed_scoped_lifecycle')
        self.assertEqual(result['analog_qualification_max_age_s'],200e-9)
        self.assertTrue(audit['selected_ctle_enabled'])
        self.assertTrue(audit['qualification_loss_bit_indices'])
        self.assertTrue(all(4000<=i<4400 for i in audit['qualification_loss_bit_indices']))
        self.assertGreater(audit['accepted_after_drought'],0)
        self.assertGreater(audit['heldout_accepted_bits'],0)
        self.assertEqual(audit['heldout_bit_errors'],0)


class OwnerCurrentGateTests(unittest.TestCase):
    def test_current_inventory_keeps_converters_on_their_own_rail(self):
        from selected_revision_check import owner_current_gate
        from baseline_envelope import P
        design=load_design();contract=design.contract;architecture=design.architecture
        result=owner_current_gate(contract,architecture,design=design)
        self.assertEqual(result["design_provenance"],design.provenance())
        self.assertEqual(result['status'],'within_mode_allocations')
        for row in result['cases']:
            self.assertAlmostEqual(sum(row['rail_current_a'].values()),row['total_chip_current_a'])
            converter_blocks=[name for name,block in architecture['blocks'].items() if block['supply']=='conv']
            self.assertAlmostEqual(row['rail_current_a']['conv'],sum(
                row['allocation']['by_block_ma'][name] for name in converter_blocks)/1000)
        self.assertEqual(set(result['selected_planning_case']['rail_current_a']),
                         {'core','conv','host','pll','rf','wire','external'})
        self.assertEqual(result['selected_planning_case']['rail_current_a']['external'],0.)
        self.assertFalse(result['physical_pin_current_qualification'])
        # Independent accounting fault: increasing an allocation is not a
        # transistor change or a selectable chip setting.
        architecture['blocks']['adc_i']['resource_allocation']['current_budget_ma']['rf_rx']+=20
        adverse=owner_current_gate(contract,architecture)
        self.assertEqual(adverse['status'],'allocation_exceeded')
        self.assertEqual(adverse['model_role'],'independent_inventory_accounting')
        self.assertIsNone(adverse['design_provenance'])
        with self.assertRaisesRegex(ValueError,'conflict'):
            owner_current_gate(contract,architecture,design=design)
        self.assertFalse(adverse['selected_planning_case']['fits_mode_current_ceiling'])


class RXDiscontinuityFaultTests(unittest.TestCase):
    def test_loaded_recovery_refreshes_analog_readiness_after_fault_wait(self):
        from selected_lifecycle import loaded_wired_recovery
        from baseline_envelope import P
        from behavioral import BehavioralChip,Assumptions
        chip=BehavioralChip(Assumptions())
        chip.attach_analog_qualification([(0.,True)],max_age_s=200e-9)
        observed=[]
        def observer(time):
            observed.append(time)
            return True  # Explicit ideal-observer control; no physical qualification.
        from unittest.mock import patch
        design=load_design()
        with patch('baseline_envelope.load_design',side_effect=AssertionError('Unexpected design reload')):
            result=loaded_wired_recovery(design.contract,design=design,
                                         chip=chip,analog_observer=observer)
        self.assertEqual(result['replaced_injected_assumptions']['startup_s'],20e-6)
        self.assertEqual(result['transport_assumptions']['startup_s'],chip.a.startup_s)
        self.assertTrue(result['independent_analog_observations'])
        self.assertTrue(result['resumed_payload_matches_receiver'])
        self.assertGreater(result['rearmed_at_s']-result['host_service_complete_s'],19.9e-6)
        self.assertGreater(len(observed),100)
        self.assertLessEqual(chip.time-observed[-1],200e-9)

    def test_loaded_cdr_rearm_keeps_peer_time_and_receiver_state(self):
        from selected_lifecycle import loaded_wired_recovery
        from baseline_envelope import P
        design=load_design()
        result=loaded_wired_recovery(design.contract,design=design)
        self.assertEqual(result['design_provenance'],design.provenance())
        self.assertEqual(result['resolved_configuration']['engine'],'wire')
        self.assertEqual(result['model_role'],'shared_transport_with_explicit_loaded_receiver_fixture')
        self.assertEqual(result['transport_basis']['encoding'],'exclusive_dense')
        self.assertEqual(result['transport_basis']['ingress_bits'],design.contract['transport']['scheduling']['ingress_bits_per_source'])
        self.assertEqual(result['transport_basis']['allocation_status'],design.contract['transport']['scheduling']['fifo_budget_status'])
        self.assertFalse(result['transport_basis']['actual_rtl_capacity_qualified'])
        self.assertEqual(result['receiver_fixture']['tau'],100e-12)
        pad=design.architecture['pad_behavioral_contract']['shared_wired_network']
        expected_cap=pad['base_shunt_cap_f_per_leg']+pad['inactive_branch_cap_f_per_leg']+2*pad['mutual_cap_f']
        self.assertAlmostEqual(result['receiver_fixture']['cap']/1e-12,expected_cap/1e-12)
        cdr=design.architecture['blocks']['cdr']['parameters']
        self.assertEqual(result['receiver_fixture']['impairment']['detector_noise_rms_s'],cdr['detector_jitter_rms_s'])
        self.assertEqual(result['receiver_fixture']['impairment']['holdover_ui'],cdr['holdover_bits'])
        self.assertGreater(result['injected_transition_gap_ui'],cdr['holdover_bits'])
        self.assertEqual(result['receiver_fixture']['impairment']['noise_rms_v'],.01)
        self.assertGreater(result['discarded_receiver_words'],4900)
        self.assertGreater(result['new_epoch'],result['old_epoch'])
        self.assertGreater(result['resumed_host_words'],500)
        self.assertTrue(result['resumed_payload_matches_receiver'])
        self.assertTrue(result['final_cdr_qualified'])

    def test_discard_preserves_live_cdr_and_leaves_future_word_uncommitted(self):
        from behavioral import RecoveredWordSource
        bits=[0,1,1,0]*1000
        live=RecoveredWordSource(bits,2.5e9,.35,100.)
        reference=RecoveredWordSource(bits,2.5e9,.35,100.)
        # Fault path has committed qualification but has not consumed its word.
        live.forecast(0);live.commit(0)
        reference.forecast(0);reference.consume(0)
        boundary=200e-9
        count=live.discard_through(boundary)
        while reference.forecast(reference.word_index)<=boundary:
            reference.consume(reference.word_index)
        self.assertEqual(count,reference.word_index)
        self.assertEqual(live.word_index,reference.word_index)
        self.assertEqual(live.words,[])
        self.assertEqual(live.phase,reference.phase)
        self.assertEqual(live.qualification_losses,reference.qualification_losses)
        self.assertGreater(live.predicted[0].last_timestamp,boundary)
        self.assertEqual(live.consume(live.word_index),reference.consume(reference.word_index))
        with self.assertRaises(ValueError):live.discard_through(20e-6)

    def test_loss_after_acquisition_faults_without_consuming_invalid_word(self):
        design=load_design()
        depth=design.contract['transport']['scheduling']['ingress_bits_per_source']
        def run(chunks):
            chip=configured_wired_chip(design,'rx')
            chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
            consumed=[]
            def source(i):consumed.append(i);return i&1023
            bound_source=chip.bind_stream_callback(source)
            args=dict(mode=1,source_hz=250e6,sample_bits=10,depth_bits=depth,directions=('rx',),epoch=chip.epoch,
                rx_source=bound_source,rx_valid=lambda i:10<=i<200,fault_on_rx_loss=True)
            for n in chunks:
                result=chip.transfer(frames=n,**args)
                if result['fault']:break
            self.assertEqual(result['fault'],'rx_qualification_lost')
            self.assertEqual(chip.state,'fault');self.assertEqual(consumed[-1],199)
            self.assertEqual(chip.stream['rx_words'],list(range(10,10+len(chip.stream['rx_words']))))
            count=len(consumed)
            with self.assertRaises(ValueError):chip.transfer(frames=1,**args)
            self.assertEqual(len(consumed),count)
            return chip,result,bound_source
        chip,whole,stale_source=run([10]);other,chunked,_=run([1]*10)
        self.assertEqual(whole['produced_bits'],chunked['produced_bits'])
        self.assertEqual(chip.stream['rx_words'],other.stream['rx_words'])
        epoch=chip.epoch
        old_words=list(chip.stream['rx_words'])
        chip.stop();self.assertGreater(chip.epoch,epoch)
        with self.assertRaises(ValueError):stale_source(0)
        chip.start();chip.advance(chip.ready_at)
        resumed=dict(mode=1,source_hz=250e6,sample_bits=10,depth_bits=depth,directions=('rx',),
            frames=8,epoch=chip.epoch,fault_on_rx_loss=True,
            rx_source=chip.bind_stream_callback(lambda i:(i+513)&1023),
            rx_valid=chip.bind_stream_callback(lambda i:i>=12))
        with self.assertRaises(ValueError):chip.transfer(**dict(resumed,epoch=epoch))
        result=chip.transfer(**resumed)
        self.assertIsNone(result['fault'])
        self.assertTrue(chip.stream['rx_ever_qualified'])
        words=chip.stream['rx_words']
        self.assertGreater(len(words),100)
        self.assertEqual(words,[(i+513)&1023 for i in range(12,12+len(words))])
        self.assertNotEqual(words[:len(old_words)],old_words)


class RetainedWiredRailTests(unittest.TestCase):
    def test_bit_held_driver_supply_enters_before_channel(self):
        from wired_envelope import physical_receiver
        bits=[0,1,1,0]*32;edges=np.arange(len(bits)+1)/2.5e9
        common=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
            rail_tones=[],delay_tones=[],rail_dc_v=3.3,signal_scale=1.,rail_modulation_location='driver')
        original=physical_receiver(bits,2.5e9,.35,100.,100e-12,2.7e-12,common,source_edges_s=edges)
        reduced=physical_receiver(bits,2.5e9,.35,100.,100e-12,2.7e-12,
            dict(common,bit_drive_scale=np.full(len(bits),.8)),source_edges_s=edges)
        for ui in np.linspace(1,100,51):self.assertAlmostEqual(reduced.voltage(float(ui)),.8*original.voltage(float(ui)),places=12)
        with self.assertRaises(ValueError):physical_receiver(bits,2.5e9,.35,100.,100e-12,2.7e-12,
            dict(common,bit_drive_scale=[1.]),source_edges_s=edges)


    def test_dynamic_rail_hook_matches_static_gain_without_timing_or_noise(self):
        from wired_envelope import physical_receiver
        bits=[0,1,1,0]*32
        base=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
            rail_tones=[],delay_tones=[],rail_dc_v=3.3,signal_scale=1.)
        static=physical_receiver(bits,2.5e9,.35,100.,100e-12,2.7e-12,base)
        dynamic=physical_receiver(bits,2.5e9,.35,100.,100e-12,2.7e-12,
            dict(base,rail_at_s=lambda t:2.97,delay_at_s=lambda t:0.))
        for ui in np.linspace(1,100,51):
            self.assertAlmostEqual(dynamic.voltage(float(ui)),.9*static.voltage(float(ui)),places=12)


class WiredLifecycleEntryTests(unittest.TestCase):
    def test_wired_tx_loss_and_restart_without_rf_fixture_state(self):
        from unittest.mock import patch
        from selected_lifecycle import wired_tx_lifecycle
        class IdealClock:
            def __init__(self,environment):pass
            def crossing_error(self,times,carrier):return np.zeros_like(times)
        from baseline_envelope import configured_environment
        from design_definition import DesignDefinition
        baseline=load_design();contract=baseline.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        contract['transport']['scheduling']['egress_bits_per_source']=1536
        design=DesignDefinition.from_documents(contract,baseline.architecture)
        environment=configured_environment(design.configure(engine='wire',direction='tx',
            reference_hz=2.5e9,host_divider=8))
        edges=np.arange(1,8001)*10e-9
        edges=edges[(edges<32e-6)|(edges>=33e-6)]
        with patch('selected_lifecycle.DeliveredClock',IdealClock):
            rows=wired_tx_lifecycle(environment,edges,loss_window_s=(32e-6,33e-6))
        self.assertEqual(rows[0]['fault'],'reference_lost')
        self.assertIsNone(rows[1]['fault'])
        self.assertTrue(all(x['payload_correct'] and x['emitted_words']>100 for x in rows))

        self.assertEqual(rows[0]['design_provenance'],design.provenance())
        self.assertAlmostEqual(rows[0]['transport_started_at_s'],31e-6)
        self.assertEqual(rows[1]['startup_guard_s'],30e-6)
        self.assertEqual(rows[0]['transport_fixture']['queue_depth_bits'],1536)
        self.assertEqual(rows[0]['transport_fixture']['prefill_bits'],768)


class RFDirectionGateTests(unittest.TestCase):
    def setUp(self):
        self.design=load_design()

    def run_gate(self,chunks,*,fault=False):
        from behavioral import BehavioralChip
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        design=self.design
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=39)
        environment=configured_environment(config)
        assumptions=selected_transport_assumptions(environment)
        chip=BehavioralChip(assumptions)
        chip.configure_numeric(engine='rf',rf=dict(sample_hz=config.sample_hz,sample_clock_source='external_lo',
            lo_hz=config.reference_hz,lo_divider=config.sample_divider,rx_cutoff_hz=9.53125e6,tx_cutoff_hz=18e6))
        chip.configure_transport('exclusive')
        # Assigned completion/settling and fault observations isolate gating.
        if fault:chip.attach_analog_qualification([(0.,True),(assumptions.startup_s+3e-6,False)])
        chip.start();chip.advance(chip.ready_at);origin=chip.time;epoch=chip.epoch
        chip.enable_rf_direction_gate(rx_completion_latency_s=18e-9)
        chip.schedule_rf_direction('tx',at_s=origin+1e-6,settle_s=2e-6)
        received=[];sent=[]
        def rx(i):received.append(i);return i
        def tx(i):return (i*73+19)&1023
        queues=design.contract['transport']['scheduling']
        depth=min(queues['ingress_bits_per_source'],queues['egress_bits_per_source'])
        args=dict(mode=1,source_hz=config.sample_hz,sample_bits=24,depth_bits=depth,epoch=epoch,
            directions=('rx','tx'),tx_prefill_bits=0,rx_source=rx,tx_source=tx,
            tx_word_observer=lambda time,word:sent.append((time,word)),
            tx_host_enable=lambda time,index:index<64 or time>=origin+3e-6)
        for frames in chunks:
            flow=chip.transfer(frames=frames,**args)
            if flow['fault']:break
        self.assertEqual(chip.epoch,epoch)
        self.assertTrue(all(origin+i/config.sample_hz<origin+1e-6+18e-9 for i in received))
        self.assertTrue(all(time>=origin+3e-6 for time,word in sent))
        bits=[(word>>b)&1 for _,word in sent for b in range(24)]
        expected=[(tx(i)>>b)&1 for i in range(1000) for b in range(10)]
        self.assertEqual(bits,expected[:len(bits)])
        return chip,flow,received,sent

    def test_actual_prefill_and_direction_change_preserve_stream(self):
        chip,flow,rx,tx=self.run_gate([40])
        self.assertIsNone(flow['fault']);self.assertTrue(tx);self.assertTrue(rx)
        other,other_flow,other_rx,other_tx=self.run_gate([7,33])
        self.assertEqual(rx,other_rx);self.assertEqual(tx,other_tx)
        self.assertEqual(chip.stream['tx_bits'],other.stream['tx_bits'])
        with self.assertRaises(ValueError):chip.schedule_rf_direction('rx',at_s=chip.time-1e-6,settle_s=2e-6)

    def test_rx_analog_warmup_precedes_sample_delivery(self):
        chip,flow,rx,tx=self.run_gate([40])
        begin=chip.time+1e-6
        chip.schedule_rf_direction('rx',at_s=begin,settle_s=2e-6)
        self.assertFalse(chip.rf_rx_analog_enabled_at(begin-1e-9))
        self.assertTrue(chip.rf_rx_analog_enabled_at(begin+1e-9))
        self.assertEqual(chip._rf_direction_at(begin+1e-6),'mute')
        self.assertEqual(chip._rf_direction_at(begin+2.1e-6),'rx')
        chip.stop()
        self.assertFalse(chip.rf_rx_analog_enabled_at(begin+3e-6))

    def test_qualification_loss_wins_over_scheduled_launch(self):
        chip,flow,rx,tx=self.run_gate([40],fault=True)
        self.assertEqual(flow['fault'],'analog_unqualified');self.assertEqual(tx,[])
        with self.assertRaises(ValueError):chip.schedule_rf_direction('rx',at_s=chip.time+1e-6,settle_s=2e-6)


class TurnaroundBudgetTests(unittest.TestCase):
    def test_positive_time_margin_does_not_hide_insufficient_storage(self):
        from selected_lifecycle import selected_turnaround_requirement
        from design_definition import DesignDefinition
        design=load_design();c=design.contract
        nominal=selected_turnaround_requirement(c,design=design)
        self.assertTrue(nominal['storage_fit'])
        self.assertTrue(nominal['transition']['clocks_kept_running'])
        self.assertTrue(nominal['transition']['preserves_stream_epoch'])
        c['transport']['scheduling']['ingress_bits_per_source']=512
        reduced_design=DesignDefinition.from_documents(c,design.architecture)
        reduced=selected_turnaround_requirement(c,design=reduced_design)
        self.assertTrue(reduced['diagnostic_windows'][0]['nonnegative_residual'])
        self.assertFalse(reduced['storage_fit'])


class SupplyBlockerRequirementTests(unittest.TestCase):
    def test_passive_isolation_bound_matches_transfer_and_dc(self):
        from selected_rf import passive_supply_isolation_requirement
        args=dict(frequency_hz=10e6,input_ripple_v=.06,output_ripple_v=.0096,
                  load_current_a=.044,capacitance_f=500e-12,input_min_v=3.267,load_min_v=2.5)
        r=passive_supply_isolation_requirement(**args)
        response=abs(1/(1+2j*np.pi*args['frequency_hz']*
            r['required_series_resistance_ohm']*args['capacitance_f']))
        self.assertAlmostEqual(response*args['input_ripple_v'],args['output_ripple_v'])
        self.assertFalse(r['fits_optimistic_rc_and_dc'])
        args['capacitance_f']=r['minimum_capacitance_from_dc_f']*1.01
        feasible=passive_supply_isolation_requirement(**args)
        self.assertTrue(feasible['fits_optimistic_rc_and_dc'])
        self.assertLess(feasible['resulting_dc_drop_v'],args['input_min_v']-args['load_min_v'])

    def test_inverse_requirement_agrees_with_explicit_sideband(self):
        from selected_rf import supply_blocker_requirement
        r=supply_blocker_requirement(carrier_hz=2.4e9,ripple_hz=10e6,ripple_peak_v=.06,
            mean_rail_v=2.930075,sensitivity_s_per_v=100e-12,delay_pole_hz=1e9,
            blocker_over_wanted_db=15.)
        self.assertTrue(r['am_floor_exceeds_allocation_with_ideal_clock'])
        self.assertEqual(r['maximum_delay_sensitivity_s_per_v_at_present_ripple'],0.)
        rejection=10**(-r['combined_first_order_additional_preselection_db']/20)
        self.assertAlmostEqual(rejection*sum((r['blocker_pm_sideband_to_wanted_amplitude'],
            r['blocker_am_sideband_to_wanted_amplitude'])),.05,places=12)
        angle=2*np.pi*np.arange(65536)/65536
        modulated=np.exp(1j*r['phase_peak_rad']*np.sin(angle))
        sideband=abs(np.mean(modulated*np.exp(-1j*angle)))*10**(15/20)
        self.assertAlmostEqual(sideband,r['blocker_pm_sideband_to_wanted_amplitude'],places=12)
        constrained=supply_blocker_requirement(carrier_hz=2.4e9,ripple_hz=10e6,
            ripple_peak_v=r['pm_only_ripple_limit_v'],mean_rail_v=2.930075,
            sensitivity_s_per_v=100e-12,delay_pole_hz=1e9,blocker_over_wanted_db=15.)
        self.assertAlmostEqual(constrained['blocker_pm_sideband_to_wanted_amplitude'],.05,places=10)


class IndependentPadPeerTests(unittest.TestCase):
    def test_canonical_receiver_record_order_fault_and_reset(self):
        from stream_codec import Receiver
        from bit_event_codec import encode_records
        rx=Receiver(1,frame_words=8,owner='wire',raw_records=True)
        records=[('data',5,3,0.),('event',7,0,0.)]
        frame=encode_records(records,0)
        out=[event for word in frame for event in rx.feed_records(word)]
        self.assertEqual(out,[('data',5,3),('event',7,0)])
        self.assertEqual(rx.sequence,1)
        with self.assertRaises(ValueError):rx.feed(0)
        bad=encode_records([],1);bad[4]^=1
        with self.assertRaises(ValueError):
            for word in bad:rx.feed_records(word)
        self.assertTrue(rx.fault)
        rx.reset();self.assertFalse(rx.fault)
        self.assertEqual([event for word in frame for event in rx.feed_records(word)],out)
        with self.assertRaises(ValueError):Receiver(1,frame_words=64,raw_records=True)

    def test_decoding_does_not_hide_bad_termination_or_slow_response(self):
        from behavioral import usb_observed_response
        design=load_design()
        for resistance,valid in ((45.,True),(15000.,False)):
            report=usb_observed_response(design=design,request_lengths=(64,),clock_phases=((0.,0.),),
                usb_data_packet=True,peer_termination_ohm=resistance)
            self.assertEqual(report['design_provenance'],design.provenance())
            for row in report['cases']:
                self.assertTrue(row['delivered'])
                self.assertEqual(row['within_fixture_swing_window'],valid)
                self.assertEqual(row['meets_budget'],row['host_word_hz']==312.5e6)

    def test_usb_lifecycle_requires_explicit_peer_transition(self):
        from behavioral import usb_pad_lifecycle
        design=load_design()
        rows=usb_pad_lifecycle(design=design)
        self.assertEqual({row['role'] for row in rows},{'host','device'})
        for row in rows:
            self.assertEqual(row['design_provenance'],design.provenance())
            self.assertTrue(row['independent_peer_passives'])
            self.assertEqual(row['pad_construction']['architecture_sha256'],
                design.provenance()['documents']['spec/analog-architecture.json'])
            self.assertEqual(row['pad_initial_controls']['local']['speed'],'fs')
            self.assertEqual(row['pad_hs_controls']['local']['speed'],'hs')
            self.assertEqual(row['pad_hs_controls']['peer']['passive_override']['term'],(45.,45.))
            self.assertEqual(row['pad_final_controls']['local']['drive_state'],'Z')
            self.assertGreater(abs(row['unmatched_peer_differential_v']-.4),.1)
            self.assertTrue(row['local_and_peer_decode'])

    def test_local_speed_cannot_silently_switch_explicit_peer_termination(self):
        from protocol_pad import SharedWiredPad
        pad=SharedWiredPad();pad.configure('usb','device','fs',attached=True)
        pad.set_peer_passives(pull_down_ohm=(15000.,15000.))
        pad.set_local_passives();pad.set_local_drive('current',node=0,current_a=.001)
        before=pad.electrical(np.array([.1,0.]),3.3)[0]
        pad.configure('usb','device','hs',attached=True)
        pad.set_local_passives();pad.set_local_drive('current',node=0,current_a=.001)
        np.testing.assert_allclose(pad.electrical(np.array([.1,0.]),3.3)[0],before)
        pad.set_peer_passives(termination_ohm=(45.,45.))
        self.assertLess(pad.electrical(np.array([.1,0.]),3.3)[0][0],0.)
        pad.set_local_drive('off');pad.set_peer_passives()
        self.assertEqual(pad.peer_passives['term'],(None,None))


class SharedTXOutputTests(unittest.TestCase):
    def test_rf_pad_waveform_matches_carrier_solution_and_chunk_continuation(self):
        from selected_rf import rf_pad_waveform,rf_pad_transfer
        carrier=2.426e9;fs=20.48e9
        for matching in (None,1/((2*np.pi*carrier)**2*8e-9)):
            parameters=dict(driver_r_ohm=40.,pad_series_ohm=4.,bond_series_ohm=.4,
                bond_loop_h=8e-9,differential_cap_f=.5e-12,series_match_f=matching)
            source=np.r_[np.zeros(100),np.ones(1900)]
            full=rf_pad_waveform(source,fs,carrier,**parameters)
            transfer=rf_pad_transfer(carrier,**parameters)
            for key in ('load_voltage','pad_voltage','driver_current'):
                self.assertAlmostEqual(abs(full[key][-1]-transfer[key]),0.,places=11)
                np.testing.assert_array_equal(full[key][:100],0.)
            refined=rf_pad_waveform(np.repeat(source,2),2*fs,carrier,**parameters)
            np.testing.assert_allclose(refined['load_voltage'][1::2],full['load_voltage'],atol=1e-11,rtol=1e-11)
            first=rf_pad_waveform(source[:700],fs,carrier,**parameters)
            second=rf_pad_waveform(source[700:],fs,carrier,initial_state=first['final_state'],**parameters)
            for key in ('load_voltage','pad_voltage','driver_current','driver_current_at_interval_start'):
                np.testing.assert_allclose(np.r_[first[key],second[key]],full[key],atol=1e-12,rtol=1e-12)
            with self.assertRaises(ValueError):
                rf_pad_waveform(source,fs,carrier*1.01,initial_state=first['final_state'],**parameters)

    def test_reactive_rf_pad_obeys_kcl_and_real_power_balance(self):
        from selected_rf import rf_pad_transfer
        f=np.array([0.,1e6,2.426e9,5e9])
        for inductance in (0.,1e-9,4e-9,8e-9):
            r=rf_pad_transfer(f,driver_r_ohm=40.,pad_series_ohm=4.,
                bond_series_ohm=.4,bond_loop_h=inductance,differential_cap_f=.5e-12)
            np.testing.assert_allclose(1-44*r['driver_current'],r['pad_voltage'],atol=1e-14)
            np.testing.assert_allclose(r['driver_current']-r['load_current'],
                2j*np.pi*f*.5e-12*r['pad_voltage'],atol=1e-14)
            np.testing.assert_allclose(.5*r['driver_current'].real,
                .5*44*abs(r['driver_current'])**2+.5*50.4*abs(r['load_current'])**2,
                atol=1e-14)
            self.assertAlmostEqual(r['load_voltage'][0].real,50/94.4)
        ideal=rf_pad_transfer(f,driver_r_ohm=40.,pad_series_ohm=4.,
            bond_series_ohm=0.,bond_loop_h=0.,differential_cap_f=0.)
        np.testing.assert_allclose(ideal['load_voltage'],50/94)

    def test_external_series_compensation_cancels_only_assigned_bond_reactance(self):
        from selected_rf import rf_pad_transfer
        fc=2.426e9;inductance=8e-9;cap=1/((2*np.pi*fc)**2*inductance)
        options=dict(driver_r_ohm=40.,pad_series_ohm=4.,bond_series_ohm=.4,differential_cap_f=.5e-12)
        matched=rf_pad_transfer(np.array([0.,fc]),bond_loop_h=inductance,series_match_f=cap,**options)
        control=rf_pad_transfer(np.array([0.,fc]),bond_loop_h=0.,**options)
        self.assertEqual(matched['load_voltage'][0],0.)
        self.assertAlmostEqual(abs(matched['load_voltage'][1]-control['load_voltage'][1]),0.,places=12)
        np.testing.assert_allclose(.5*matched['driver_current'].real,
            .5*44*abs(matched['driver_current'])**2+.5*50.4*abs(matched['load_current'])**2,atol=1e-14)

    def test_pad_resistance_changes_loaded_power_and_current_consistently(self):
        from selected_rf import transmit_output
        wave=.2*np.exp(1j*np.linspace(0,2*np.pi,512,endpoint=False))
        rails=np.full(len(wave),3.);phase=np.zeros(len(wave))
        bare,_,_=transmit_output(wave,rails,phase)
        loaded,checks,clipped=transmit_output(wave,rails,phase,pad_series_ohm=4.)
        np.testing.assert_allclose(loaded['load_power_w'],bare['load_power_w']*(90/94)**2)
        self.assertTrue(checks['within_declared_compliance'])
        self.assertFalse(np.any(clipped))
        with self.assertRaises(ValueError):transmit_output(wave,rails,phase,pad_series_ohm=-1.)

    def test_inverse_local_rail_matches_frozen_waveform_port(self):
        from selected_lifecycle import tx_local_supply_requirement
        from selected_rf import transmit_output
        wave=.25*np.exp(1j*np.linspace(0,2*np.pi,1024,endpoint=False))
        def output(v):
            return transmit_output(wave,np.full(len(wave),v),np.zeros(len(wave)),nominal_gain=5.36)
        port,electrical,_=output(3.)
        trace={'stages':[{}, {'tx_rf_port':dict(electrical=electrical,
            nominal_gain_requirement=5.36,
            data_interval_power={'mean_load_power_w':float(np.mean(port['load_power_w']))})}]}
        contract={'generic_configuration_target':{'tx_port_power_goal':{'mean_load_power_dbm':0.}}}
        requirement=tx_local_supply_requirement(contract,trace,
            primitive_reason='Independent constant-envelope square-law inverse calculation')
        self.assertEqual(requirement['model_role'],'independent_mathematical_fixture')
        floor=requirement['minimum_instantaneous_rail_for_frozen_waveform_v']
        predicted,checks,clipped=output(floor)
        self.assertTrue(checks['within_declared_compliance'])
        self.assertFalse(np.any(clipped))
        self.assertAlmostEqual(float(np.mean(predicted['load_power_w'])),.001,places=12)
        below,_,_=output(floor*.99)
        self.assertLess(float(np.mean(below['load_power_w'])),.001)

    def test_steady_rail_success_does_not_certify_dynamic_rail_history(self):
        from selected_rf import tx_amplitude_bound,transmit_output
        from pathlib import Path
        design=load_design()
        config=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64,tx_gain=5.36)
        req=design.contract['generic_configuration_target']['tx_amplitude_operating_requirement']
        options=dict(nominal_gain=config.resolved_tx_gain,
            driver_parameters=design.architecture['blocks']['rfdriver']['parameters'],
            output_parameters=design.architecture['model_assumptions']['rf_output']['parameters'])
        from baseline_envelope import configured_environment
        rail_bias=configured_environment(config)['inventory_current_a']['rf']
        bound=tx_amplitude_bound(req,**options)
        self.assertFalse(bound['within_declared_headroom'])
        self.assertFalse(bound['correlated_supply_bound']['within_declared_headroom'])
        # Steady endpoints still work; retained high-rail gain prevents using
        # that result as a certificate for arbitrary rail histories.
        z=req['reconstructed_complex_peak_v']*np.exp(1j*np.linspace(0,2*np.pi,257))
        for v in np.linspace(*req['supply_interval_v'],41):
            _,electrical,clipped=transmit_output(z,np.full(len(z),v),np.zeros(len(z)),rail_bias_a=rail_bias,**options)
            self.assertTrue(electrical['within_declared_compliance'])
            self.assertFalse(np.any(clipped))
        # Independent out-of-range numerical counterexample, not a legal chip setting.
        self.assertFalse(tx_amplitude_bound(req,nominal_gain=8.)['correlated_supply_bound']['within_declared_headroom'])

    def test_spectral_diagnostic_recovers_known_sideband_power(self):
        from selected_rf import tx_spectral_diagnostic
        fs=160e6;t=np.arange(16384)/fs
        wave=np.exp(2j*np.pi*1e6*t)+.1*np.exp(2j*np.pi*20e6*t)
        r=tx_spectral_diagnostic(wave,fs)
        self.assertAlmostEqual(r['relative_band_power_db']['upper_adjacent'],-20.,places=5)
        self.assertLess(r['relative_band_power_db']['lower_adjacent'],-90.)
        with self.assertRaises(ValueError):tx_spectral_diagnostic(np.zeros(100),fs)

    def test_amplitude_requirement_bounds_all_iq_angles_at_supply_endpoints(self):
        from selected_rf import tx_amplitude_bound,transmit_output
        from pathlib import Path
        design=load_design()
        config=design.configure(engine='rf',direction='tx',reference_hz=2.4e9,sample_divider=64,tx_gain=4.5)
        driver=design.architecture['blocks']['rfdriver']['parameters']
        options=dict(nominal_gain=config.resolved_tx_gain,driver_parameters=driver,
            output_parameters=design.architecture['model_assumptions']['rf_output']['parameters'])
        requirement=design.contract['generic_configuration_target']['tx_amplitude_operating_requirement']
        from baseline_envelope import configured_environment
        rail_bias=configured_environment(config)['inventory_current_a']['rf']
        bound=tx_amplitude_bound(requirement,**options)
        self.assertTrue(bound['within_declared_headroom'])
        z=requirement['reconstructed_complex_peak_v']*np.exp(1j*np.linspace(0,2*np.pi,2049))
        for supply in requirement['supply_interval_v']:
            port,electrical,clipped=transmit_output(z,np.full(len(z),supply),np.zeros(len(z)),rail_bias_a=rail_bias,**options)
            self.assertFalse(np.any(clipped));self.assertTrue(electrical['within_declared_compliance'])
            self.assertLessEqual(float(max(abs(port['envelope_v'])))*(driver['source_r_ohm_differential']+driver['load_ohm_differential'])/driver['load_ohm_differential'],bound['open_peak_bound_v'])

    def test_disabled_tail_cannot_emit_and_port_power_is_conserved(self):
        from selected_rf import transmit_output
        z=np.full(16,.2+.1j);rails=np.full(16,3.0);phase=np.linspace(0,1,16)
        off,_,_=transmit_output(z,rails,phase,available_current_a=np.zeros(16))
        np.testing.assert_array_equal(off['envelope_v'],np.zeros(16))
        port,electrical,_=transmit_output(z,rails,phase)
        self.assertTrue(electrical['within_declared_compliance'])
        np.testing.assert_allclose(port['load_power_w'],abs(port['envelope_v'])**2/100)
        np.testing.assert_allclose(port['source_dissipation_w'],port['load_power_w']*.8)
        self.assertEqual(electrical['total_rail_bias_a'],.044)


class WidebandConfigurationTests(unittest.TestCase):
    def test_inventory_gain_and_converter_model_are_not_silently_ignored(self):
        from selected_rf import wideband_receive
        from pathlib import Path
        architecture=load_design().architecture
        codes=architecture['blocks']['pga_i']['parameters']['gain_db']
        self.assertEqual(max(codes),42.)
        with self.assertRaisesRegex(ValueError,'PGA gain'):
            wideband_receive({},gain_settings_db=(54.,),gain_hypothesis_reason='Requirement-search control above the selected PGA range',gain_codes_db=codes)
        with self.assertRaisesRegex(ValueError,'causal SAR'):
            wideband_receive({},comparator_model=dict(tau_s=50e-12))

    def test_selected_passband_is_configurable_and_preserved(self):
        from resource_configuration import validate_rf_settings
        from selected_rf import _analog_prototype
        from scipy import signal
        from pathlib import Path
        contract=load_design().contract
        cutoff=contract['generic_configuration_target']['rx_filter_cutoff_range_hz'][1]
        validate_rf_settings(sample_hz=37.5e6,tx_cutoff_hz=3e6,rx_cutoff_hz=cutoff,
            sample_clock_source='external_lo',lo_hz=2.4e9,lo_divider=64)
        b,a=_analog_prototype('rx_finite_zero')
        _,h=signal.freqs(b,a,worN=np.linspace(0,9.53125e6,4097)/cutoff)
        self.assertLessEqual(float(np.max(-20*np.log10(abs(h)))),1.+1e-9)
        with self.assertRaises(ValueError):
            validate_rf_settings(rx_cutoff_hz=cutoff+1.)


class DeliveredIQTests(unittest.TestCase):
    def test_host_boundary_does_not_invent_partial_sample(self):
        from selected_lifecycle import delivered_iq_words
        iq=[(-2048,2047),(-1,0),(17,-23)]
        bits=[]
        for i,q in iq:
            word=(i&4095)|((q&4095)<<12)
            bits.extend((word>>j)&1 for j in range(24))
        host=[sum(bits[j+k]<<k for k in range(10)) for j in range(0,70,10)]
        actual,partial=delivered_iq_words(host)
        np.testing.assert_array_equal(actual,iq[:2]);self.assertEqual(partial,22)
        empty,partial=delivered_iq_words([])
        self.assertEqual(empty.shape,(0,2));self.assertEqual(partial,0)


class SharedRFFrontendTests(unittest.TestCase):
    def test_numeric_gain_step_is_causal_and_settles_in_voltage(self):
        from selected_rf import settling_gain
        import numpy as np
        t=np.array([0.,1e-6,2e-6,11e-6])
        g=settling_gain(t,20.,initial_db=0.,tau_s=1e-6,command_s=1e-6)
        np.testing.assert_allclose(g[:2],[1.,1.])
        self.assertAlmostEqual(g[2],10.-9./np.e)
        self.assertLess(abs(g[-1]-10.),.001)
        np.testing.assert_allclose(settling_gain(t,20.,initial_db=0.,command_s=1e-6),[1.,10.,10.,10.])
        with self.assertRaises(ValueError):settling_gain(t,20.,tau_s=-1.)

    def test_frontend_noise_figure_and_linearity_are_independent_inputs(self):
        from selected_rf import receive_frontend
        import numpy as np
        t=np.arange(1024)/100e6
        def run(drive,nf,iip3,noise):
            return receive_frontend(drive,t,np.full(len(t),3.3),np.zeros(len(t)),
                sample_hz=100e6,wanted_dbm=-10.,blocker_dbm=None,
                noise_figure_db=nf,input_iip3_dbm=iip3,
                noise_rng=np.random.default_rng(11) if noise else None)[0]
        quiet=np.zeros(len(t),complex)
        low=run(quiet,6.,0.,True);high=run(quiet,12.,0.,True)
        np.testing.assert_allclose(high,low*10**(6/20),rtol=1e-12)
        drive=np.ones(len(t),complex)
        self.assertGreater(np.mean(abs(run(drive,6.,10.,False))),
                           np.mean(abs(run(drive,6.,0.,False))))
        with self.assertRaises(ValueError):run(quiet,-1.,0.,True)

    def test_partitioned_record_preserves_signal_noise_and_filter_state(self):
        from selected_rf import receive_frontend,analog_filter
        rate=160e6;t=np.arange(320)/rate
        drive=np.exp(2j*np.pi*3e6*t)
        rails=3.0+.04*np.sin(2*np.pi*7e6*t)
        phase=.03*np.sin(2*np.pi*11e6*t)
        whole,_=receive_frontend(drive,t,rails,phase,sample_hz=rate,
            noise_rng=np.random.default_rng(17))
        rng=np.random.default_rng(17);pieces=[];filtered=[];state=None
        for a,b in ((0,71),(71,199),(199,320)):
            x,_=receive_frontend(drive[a:b],t[a:b],rails[a:b],phase[a:b],
                sample_hz=rate,noise_rng=rng)
            pieces.append(x);capture={}
            filtered.append(analog_filter(x,rate,family='rx_finite_zero',
                cutoff_hz=9.53125e6,initial_state=state,state_capture=capture))
            state=capture
        np.testing.assert_array_equal(np.concatenate(pieces),whole)
        reference=analog_filter(whole,rate,family='rx_finite_zero',cutoff_hz=9.53125e6)
        np.testing.assert_allclose(np.concatenate(filtered),reference,rtol=1e-12,atol=1e-15)


class BaselineBudgetTests(unittest.TestCase):
    def test_host_load_ramp_preserves_state_and_matches_dc_ownership(self):
        from robustness_envelope import LocalLoadTransient
        n=shared_board_candidate();n['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        rail=LocalLoadTransient(n,include_host_load=True,clock_pole_hz=1e9,
                                clock_sensitivity_s_per_v=25e-12)
        rail.ramp_to(0.,.02,100e-9,host_increment_a=.008)
        rail.advance(50e-9);before=rail.state.copy()
        rail.ramp_to(50e-9,.03,100e-9,host_increment_a=.01)
        np.testing.assert_array_equal(rail.state,before)
        rail.advance(30e-6)
        expected=-(n['network']['feed_r']+n['network']['package_r']+n['return_r_ohm'])*.03-(n['network']['feed_r']+n['return_r_ohm'])*.01
        self.assertAlmostEqual(rail.voltage,expected,places=8)
        self.assertAlmostEqual(rail.clock_delay,expected*25e-12,places=18)

    def test_load_commands_invalidate_timing_callbacks(self):
        from robustness_envelope import LocalLoadTransient
        n=shared_board_candidate();n['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        rail=LocalLoadTransient(n,clock_pole_hz=1e9,clock_sensitivity_s_per_v=25e-12)
        rail.ramp_to(0.,.052,20e-9)
        event=rail.bind_clock_events([10e-9,30e-9],origin=0.)
        first=event(0);rail.advance(25e-9)
        self.assertEqual(event(0),first)  # Same scheduled trajectory; ramp completion is not a new command.
        with self.assertRaises(ValueError):event(-1)
        with self.assertRaises(ValueError):event(2)
        before=rail.state.copy();rail.ramp_to(25e-9,0.,20e-9)
        np.testing.assert_array_equal(rail.state,before)
        with self.assertRaises(ValueError):event(1)
        new=rail.bind_clock_events([30e-9],origin=25e-9)
        self.assertGreater(new(0),0.)
        rail.set_slope(25e-9,0.)
        with self.assertRaises(ValueError):new(0)

    def test_duplex_wired_clocks_are_independent_and_chunk_invariant(self):
        import sys
        from pathlib import Path
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        design=load_design()
        queues=design.contract['transport']['scheduling']
        depth=min(queues['ingress_bits_per_source'],queues['egress_bits_per_source'])
        prefill=depth//2
        def run(chunks):
            chip=configured_wired_chip(design,'duplex')
            chip.start();chip.advance(chip.ready_at);origin=chip.time;emitted=[];received=[]
            def source(i):received.append(i);return (i*37+11)%1024
            args=dict(mode=1,source_hz=250e6,sample_bits=10,depth_bits=depth,tx_prefill_bits=prefill,epoch=chip.epoch,
                rx_source=source,tx_source=lambda i:(i*73+19)%1024,
                rx_event_time=lambda i:(i+.75)/250e6,
                tx_event_time=lambda i:(i+1.25)/250e6,
                tx_word_observer=lambda time,word:emitted.append((time,word)))
            for frames in chunks:
                result=chip.transfer(frames=frames,**args);self.assertIsNone(result['fault'])
            for i,(time,word) in enumerate(emitted):
                self.assertAlmostEqual((time-origin)*250e6,i+1.25,places=8)
            bits=[(word>>bit)&1 for time,word in emitted for bit in range(10)]
            expected=[0]*prefill+[((i*73+19)%1024>>bit)&1 for i in range(400) for bit in range(10)]
            self.assertEqual(bits,expected[:len(bits)])
            words=list(chip.stream['rx_words'])
            self.assertEqual(words,[(i*37+11)%1024 for i in range(len(words))])
            self.assertNotEqual(len(received),len(emitted))
            return emitted,words,chip.time,chip.stream['tx_event_index']
        self.assertEqual(run([4]),run([1,1,2]))

    def test_package_clock_preview_preserves_live_state(self):
        from robustness_envelope import LocalLoadTransient
        n=shared_board_candidate();n['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        model=LocalLoadTransient(n,clock_pole_hz=1e9,clock_sensitivity_s_per_v=25e-12)
        model.ramp_to(0.,.052,20e-9)
        state=model.state.copy();deadline=model.ramp_end
        times=np.arange(1,101)*1e-9;edges=model.preview_clock_edges(times)
        np.testing.assert_array_equal(model.state,state)
        self.assertEqual(model.time,0.);self.assertEqual(model.ramp_end,deadline)
        self.assertEqual(model._transitions,{})
        self.assertTrue(np.any(edges!=times))
        for time,edge in zip(times,edges):
            model.advance(float(time));self.assertAlmostEqual(edge-time,model.clock_delay,places=22)
        with self.assertRaises(ValueError):model.preview_clock_edges([model.time-1e-9])

    def test_package_timing_filter_uses_continuous_rail_state(self):
        from scipy.integrate import solve_ivp
        from robustness_envelope import LocalLoadTransient,local_load_state_space
        n=shared_board_candidate();n['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        base=local_load_state_space(n);pole=2*np.pi*1e9;slope=.052/20e-9
        model=LocalLoadTransient(n,clock_pole_hz=1e9,clock_sensitivity_s_per_v=25e-12)
        model.set_slope(0.,slope)
        def derivative(t,y):
            voltage=(base.C@y[:5]+base.D[:,0]*slope).item()
            return np.r_[base.A@y[:5]+base.B[:,0]*slope,pole*(voltage-y[5])]
        reference=solve_ivp(derivative,(0,20e-9),np.zeros(6),method='Radau',rtol=1e-9,atol=1e-12)
        self.assertTrue(reference.success);model.advance(20e-9)
        np.testing.assert_allclose(model.state,reference.y[:,-1],rtol=1e-7,atol=1e-10)
        delay=model.clock_delay;model.set_slope(20e-9,0.)
        self.assertEqual(delay,model.clock_delay)
        model.advance(2e-6)
        self.assertAlmostEqual(model.clock_delay,model.voltage*25e-12,places=19)

    def test_scheduled_package_ramp_and_interrupted_recovery(self):
        from robustness_envelope import LocalLoadTransient
        n=shared_board_candidate();n['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        scheduled=LocalLoadTransient(n);explicit=LocalLoadTransient(n)
        scheduled.ramp_to(0.,.052,100e-9);explicit.set_slope(0.,.052/100e-9)
        scheduled.advance(40e-9);explicit.advance(40e-9)
        before=scheduled.state.copy()
        scheduled.ramp_to(40e-9,0.,20e-9)
        np.testing.assert_array_equal(scheduled.state,before)
        explicit.set_slope(40e-9,-explicit.state[4]/20e-9)
        explicit.set_slope(60e-9,0.);explicit.advance(200e-9)
        scheduled.advance(200e-9)
        np.testing.assert_allclose(scheduled.state,explicit.state,rtol=1e-8,atol=1e-10)
        self.assertIsNone(scheduled.ramp_end)
        self.assertAlmostEqual(scheduled.state[4],0.,places=12)
        self.assertEqual(scheduled.slope,0.)
        scheduled.ramp_to(200e-9,.052,20e-9);scheduled.advance(240e-9)
        self.assertAlmostEqual(scheduled.state[4],.052,places=12)
        before=scheduled.state.copy()
        with self.assertRaises(ValueError):scheduled.ramp_to(240e-9,0.,0.)
        np.testing.assert_array_equal(scheduled.state,before)

    def test_persistent_package_state_matches_independent_integration(self):
        from scipy.integrate import solve_ivp
        from robustness_envelope import LocalLoadTransient
        network=shared_board_candidate()
        network['network'].update(die_c=500e-12,die_esr=.5,die_esl=.2e-9)
        continuous=LocalLoadTransient(network);chunked=LocalLoadTransient(network)
        state=np.zeros(5);start=0.
        for stop,slope in ((20e-9,2.6e6),(70e-9,0.),(90e-9,-2.6e6),(150e-9,0.)):
            previous=continuous.state.copy()
            continuous.set_slope(start,slope);chunked.set_slope(start,slope)
            np.testing.assert_array_equal(continuous.state,previous)
            a,b=continuous.system.A,continuous.system.B[:,0]
            independent=solve_ivp(lambda t,y:a@y+b*slope,(start,stop),state,
                                  method='Radau',rtol=1e-9,atol=1e-12)
            self.assertTrue(independent.success)
            state=independent.y[:,-1]
            continuous.advance(stop)
            for time in np.linspace(start,stop,18)[1:]:chunked.advance(float(time))
            np.testing.assert_allclose(continuous.state,state,rtol=1e-7,atol=1e-10)
            np.testing.assert_allclose(chunked.state,continuous.state,rtol=1e-8,atol=1e-11)
            self.assertAlmostEqual(chunked.voltage,continuous.voltage,places=10)
            start=stop
        self.assertAlmostEqual(continuous.state[4],0.,places=12)
        previous=continuous.state.copy()
        with self.assertRaises(ValueError):continuous.set_slope(start,float('nan'))
        with self.assertRaises(ValueError):continuous.advance(start-1e-9)
        np.testing.assert_array_equal(continuous.state,previous)

    def test_load_transitions_preserve_energy_and_match_independent_ode(self):
        import sys
        from pathlib import Path
        from scipy.integrate import solve_ivp
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import SharedRail
        # Underdamped, critically damped, and overdamped feed networks.
        # Independent KCL/KVL integration checks both state and integrated load.
        for resistance in (2.,4.,8.):
            rail=SharedRail(resistance_ohm=resistance,capacitance_f=500e-12,
                            inductance_h=2e-9,bias_current_a=.04)
            state=np.zeros(2);time=0.;charge=0.
            for end,new_load in ((10e-9,.12),(17e-9,.01),(30e-9,.08),(50e-9,0.)):
                old_load=rail.bias
                solution=solve_ivp(lambda t,y: [(old_load-y[1])/rail.c,
                    (y[0]-rail.r*y[1])/rail.l],(time,end),state,
                    rtol=1e-10,atol=1e-12)
                charge+=old_load*(end-time)
                rail.set_bias_current(end,new_load)
                state=solution.y[:,-1];time=end
                np.testing.assert_allclose([rail.droop,rail.current],state,rtol=1e-8,atol=1e-10)
                self.assertAlmostEqual(rail.bias_charge,charge,places=18)
                stored=(rail.droop,rail.current,rail.phase,rail.charge,rail.bias_charge)
                rail.set_bias_current(end,new_load)
                self.assertEqual(stored,(rail.droop,rail.current,rail.phase,rail.charge,rail.bias_charge))
            snapshot=vars(rail).copy()
            for bad_time,bad_load in ((time,-1.),(time,float('nan')),(time-1e-9,.1)):
                with self.assertRaises(ValueError):rail.set_bias_current(bad_time,bad_load)
                self.assertEqual(vars(rail),snapshot)

    def test_selected_differential_clock_routes_both_legs_and_charges_bias_once(self):
        from baseline_envelope import configured_environment,clock_screen_environment,reference_payload_environment,P
        from reference_input_probe import paired_environment
        design=load_design();c=design.contract
        for mode,carrier in [('rf',2.4e9),('rf',2.484e9),('wire',2.5e9)]:
            raw,_=clock_screen_environment(design,mode,carrier)
            e,r=reference_payload_environment(raw,dict(link_r_ohm=1e-5),False)
            self.assertIsNotNone(e)
            self.assertNotIn('internal_switching_loads',raw)
            self.assertEqual(sum(x['mean_a'] for x in e['internal_switching_loads']),.030)
            self.assertEqual(e['external_clock_input']['topology'],'differential')
            self.assertAlmostEqual(e['ledger']['total_chip_supply_current_a'],
                raw['inventory_current_report']['total_ma']/1000)
            self.assertEqual(e['local_supply_sensitivity_ps_per_mv'],
                c['physical_services']['external_clock_input']['supply_sensitivity_ps_per_mv'])
            self.assertEqual(e['reference_load_parameters']['differential'],c['physical_services']['external_clock_input']['input_model'])
            self.assertEqual(len(r['per_leg_bound_v']),2)
            self.assertLess(max(r['per_leg_bound_v']),.6)
            control,_=paired_environment(dict(raw,internal_switching_loads=e['internal_switching_loads']),e['reference_load_parameters']['differential'],ledger=e['ledger'])
            np.testing.assert_allclose(e['periodic_clock']['edges_s'],control['periodic_clock']['edges_s'],rtol=0,atol=1e-20)
        rejected,_=reference_payload_environment(raw,dict(link_r_ohm=1e-5),False,source_peak_v=4.)
        self.assertIsNone(rejected)
        with self.assertRaises(ValueError):reference_payload_environment(raw,{},True)

    def test_internal_switching_charge_fourier_ports_and_budget(self):
        from baseline_envelope import internal_switching_sources
        rate=156.25e6;tau=.2e-9;mean=.020;origin=.17/rate
        load=dict(owner='core',mean_a=mean,event_hz=rate,tau_s=tau,origin_s=origin,harmonics=8)
        ports=internal_switching_sources([load]);period=1/rate
        # Independent time-domain integration of positive periodic pulses.
        t=(np.arange(131072)+.5)*period/131072
        age=(t-origin)%period
        current=sum(mean/rate*(age+j*period)**2*np.exp(-(age+j*period)/tau)/(2*tau**3) for j in range(4))
        self.assertAlmostEqual(float(current.mean()),mean,places=10)
        for k in (1,3,8):
            measured=2*np.mean(current*np.exp(-2j*np.pi*k*rate*t))
            np.testing.assert_allclose(ports[k*rate][3],measured,rtol=1e-8,atol=1e-12)
            self.assertEqual(sum(ports[k*rate]),0)
            self.assertEqual(ports[k*rate][1],-ports[k*rate][3])
        with self.assertRaises(ValueError):internal_switching_sources([load,load,load])
        self.assertEqual(internal_switching_sources([]),{})

    def test_supply_driven_channel_against_augmented_state_space(self):
        from scipy import signal,linalg
        from wired_envelope import physical_receiver
        bits=[1,0,1];edges=np.array([.2,.7,1.3,1.8])
        tones=[dict(frequency_hz=.73e9,clock_rail_voltage_peak_v=.23,voltage_phase_rad=.31),
               dict(frequency_hz=2.17e9,clock_rail_voltage_peak_v=.17,voltage_phase_rad=-.8)]
        for load_tau,ctle in ((.135,True),(.135,False),(.1,False)):
            q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
                signal_scale=.9,rail_dc_v=2.9,rail_tones=tones,rail_modulation_location='driver')
            denominator=np.polymul([.1,1],[load_tau,1]);numerator=[1.]
            if ctle:
                q.update(ctle_zero_s=200e-12,ctle_pole_s=80e-12)
                denominator=np.polymul(denominator,[.08,1]);numerator=[.2,1]
            rx=physical_receiver(bits,2.5e9,0.,0.,100e-12,load_tau*1e-9/50,q,
                source_edges_s=edges*1e-9,hold_final_level=True)
            # Independent real companion states plus real oscillator states,
            # all in nanoseconds. No modal residues or particular solution.
            a,b,c,d=signal.tf2ss(numerator,denominator);n=len(a)
            for sample in (.45,.7001,.85,1.45,2.0):
                state=np.zeros(n)
                for i,bit in enumerate(bits):
                    finish=sample if i==len(bits)-1 else min(sample,edges[i+1])
                    duration=finish-edges[i]
                    if duration<=0:break
                    aug=np.zeros((n+1+2*len(tones),n+1+2*len(tones)))
                    aug[:n,:n]=a;sign=1 if bit else -1;aug[:n,n]=sign*b[:,0]
                    extra=[1.]
                    for k,tone in enumerate(tones):
                        w=2*np.pi*tone['frequency_hz']*1e-9;j=n+1+2*k
                        aug[:n,j]=sign*b[:,0]*tone['clock_rail_voltage_peak_v']/q['rail_dc_v']
                        aug[j,j+1]=-w;aug[j+1,j]=w
                        theta=w*edges[i]+tone['voltage_phase_rad']
                        extra.extend([np.cos(theta),np.sin(theta)])
                    state=(linalg.expm(aug*duration)@np.r_[state,extra])[:n]
                    if finish==sample:break
                expected=.4*q['signal_scale']*float((c@state).item())
                self.assertAlmostEqual(rx.voltage(sample*1e-9*2.5e9),expected,places=10)

    def test_driver_rail_tone_gets_channel_filtering_and_dc_limit(self):
        from wired_envelope import physical_receiver
        rate=2.5e9;frequency=2e9;phase=.37;time=99.3e-9
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,
            signal_scale=.9,rail_dc_v=3.,rail_modulation_location='driver',
            rail_tones=[dict(frequency_hz=frequency,clock_rail_voltage_peak_v=.3,voltage_phase_rad=phase)],
            ctle_zero_s=200e-12,ctle_pole_s=80e-12)
        rx=physical_receiver([1],rate,0.,0.,100e-12,2.7e-12,q,source_edges_s=[0.,200e-9])
        s=2j*np.pi*frequency
        h=(1+s*200e-12)/((1+s*100e-12)*(1+s*135e-12)*(1+s*80e-12))
        expected=.36*(1+.1*np.real(h*np.exp(2j*np.pi*frequency*time+1j*phase)))
        self.assertAlmostEqual(rx.voltage(time*rate),expected,places=11)
        bits=[1,0,1,1];edges=np.array([0.,.45,.91,1.37,1.9])*1e-9
        driver=dict(q,rail_tones=[])
        receiver=dict(driver,rail_modulation_location='receiver')
        a=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,driver,source_edges_s=edges)
        b=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,receiver,source_edges_s=edges)
        for t in np.linspace(.05e-9,1.85e-9,40):
            self.assertAlmostEqual(a.voltage(t*rate),b.voltage(t*rate),places=11)

    def test_actual_tx_events_preserve_transport_bits_and_chunking(self):
        from baseline_envelope import configured_environment,clock_screen_environment,single_ended_reference_payload_environment,wired_transmit_transport,P
        design=load_design();contract=design.contract
        e,_=single_ended_reference_payload_environment(configured_environment(design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)),
            dict(link_r_ohm=1e-5),False,source_peak_v=.75)
        whole,trace=wired_transmit_transport(e,frames=16,host_service_ppm=-100.)
        split,other=wired_transmit_transport(e,frames=16,host_service_ppm=-100.,chunks=(3,5,8))
        self.assertEqual(whole,split)
        self.assertEqual(trace['bits'],other['bits'])
        np.testing.assert_array_equal(trace['edges_s'],other['edges_s'])
        self.assertIsNone(whole['flow']['fault'])
        self.assertEqual(whole['payload_bit_errors'],0)
        self.assertGreater(whole['flow']['tx']['minimum_bits'],0)
        self.assertLess(whole['maximum_word_event_error_s'],1e-15)
        self.assertAlmostEqual(whole['flow']['host_capacity_bps'],312.5e6*10*59/64)
        # This independent expected source includes the real prefill bits,
        # followed by host-supplied data; no transport output feeds this oracle.
        expected=np.random.default_rng(9021).integers(0,2,2600).tolist()
        self.assertEqual(trace['bits'],expected)

    def test_wired_tx_queue_capacity_propagates_from_shared_contract(self):
        from baseline_envelope import configured_environment,wired_transmit_transport
        from design_definition import DesignDefinition
        original=load_design();contract=original.contract
        contract['transport']['scheduling']['egress_bits_per_source']=1536
        design=DesignDefinition.from_documents(contract,original.architecture)
        environment=configured_environment(design.configure(engine='wire',direction='tx',
            reference_hz=2.5e9,host_divider=8))
        result,_=wired_transmit_transport(environment,frames=16)
        self.assertEqual(result['flow']['depth_bits'],1536)
        self.assertEqual(result['flow']['tx']['prefill_bits'],768)
        self.assertEqual(result['payload_bit_errors'],0)
        self.assertEqual(result['transport_fixture']['prefill_policy'],'half_capacity_floor')
        # A different shared H2D service clock must change actual transport
        # capacity, while frames retain the scheduler's nominal time unit.
        contract['transport']['profiles']['ddr156']['clock_hz']=150e6
        slower=DesignDefinition.from_documents(contract,original.architecture)
        slow_environment=configured_environment(slower.configure(engine='wire',direction='tx',
            reference_hz=2.5e9,host_divider=8))
        slow,_=wired_transmit_transport(slow_environment,frames=16)
        self.assertEqual(slow['resolved_configuration']['h2d_word_hz'],300e6)
        self.assertAlmostEqual(slow['flow']['h2d_capacity_bps'],300e6*10*59/64)
        self.assertEqual(slow['payload_bit_errors'],0)
        # This intentionally reduced queue is an ownership probe, not a
        # passing startup design. Verify rate sensitivity in real host events.
        self.assertEqual(result['flow']['fault'],'underflow')
        self.assertEqual(slow['flow']['fault'],'underflow')
        self.assertLess(slow['flow']['host_staging']['captured_bits'],
                        result['flow']['host_staging']['captured_bits'])
        del environment['transport_parameters']['legacy_tx_queue_bits']
        with self.assertRaisesRegex(ValueError,'shared legacy TX queue'):
            wired_transmit_transport(environment,frames=1)

    def test_observed_reference_halt_drains_actual_tx_queue(self):
        from baseline_envelope import configured_environment,clock_screen_environment,single_ended_reference_payload_environment,wired_transmit_transport,P
        design=load_design();contract=design.contract
        e,_=single_ended_reference_payload_environment(configured_environment(design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)),
            dict(link_r_ohm=1e-5),False,source_peak_v=.75)
        result,_=wired_transmit_transport(e,frames=16,reference_stop_s=.5e-6)
        self.assertEqual(result['flow']['fault'],'underflow')
        self.assertEqual(result['chip_state'],'fault')
        self.assertEqual(result['payload_bit_errors'],0)
        self.assertLess(result['flow']['tx']['pending_bits'],10)
        self.assertGreater(result['flow']['simulated_s'],.5e-6)
        self.assertLess(result['flow']['simulated_s'],2e-6)

    def test_nonuniform_serial_edges_against_two_pole_step(self):
        from wired_envelope import physical_receiver
        rate=2.5e9;a=100e-12;b=135e-12
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.)
        edge=.2e-9
        rx=physical_receiver([1,1],rate,0.,0.,a,b/50,q,source_edges_s=[edge,.7e-9,1.3e-9])
        self.assertEqual(rx.voltage(.1e-9*rate),0.)
        for time in (.3e-9,.65e-9,.8e-9,1.2e-9):
            elapsed=time-edge
            expected=.4*(1-(a*np.exp(-elapsed/a)-b*np.exp(-elapsed/b))/(a-b))
            self.assertAlmostEqual(rx.voltage(time*rate),expected,places=12)
        bits=[1,0,1,1,0,0,1,0]
        normal=physical_receiver(bits,rate,0.,0.,a,b/50,q)
        explicit=physical_receiver(bits,rate,0.,0.,a,b/50,q,source_edges_s=np.arange(len(bits)+1)/rate)
        for time in np.linspace(.1,len(bits)-.1,71):
            self.assertAlmostEqual(normal.voltage(time),explicit.voltage(time),places=12)
        with self.assertRaises(ValueError):
            physical_receiver(bits,rate,0.,0.,a,b/50,q,source_edges_s=np.zeros(len(bits)+1))

    def test_nonuniform_serial_ctle_against_state_space(self):
        from scipy import signal,linalg
        from wired_envelope import physical_receiver
        q=dict(jitter_rms_s=0.,jitter_hz=25e6,noise_rms_v=0.,offset_v=0.,ctle_zero_s=200e-12,ctle_pole_s=80e-12)
        bits=[1,0,1];edges=np.array([.2,.7,1.3,1.8])
        rx=physical_receiver(bits,2.5e9,0.,0.,100e-12,2.7e-12,q,source_edges_s=edges*1e-9)
        # Independent real companion-state evolution, in nanosecond units.
        denominator=np.polymul(np.polymul([.1,1],[.135,1]),[.08,1])
        a,b,c,d=signal.tf2ss([.2,1],denominator)
        augmented=np.zeros((4,4));augmented[:3,:3]=a;augmented[:3,3]=b[:,0]
        for time in (.45,.85,1.45):
            state=np.zeros(3)
            for i,bit in enumerate(bits):
                duration=min(time,edges[i+1])-edges[i]
                if duration<=0:break
                transition=linalg.expm(augmented*duration)
                state=transition[:3,:3]@state+transition[:3,3]*(1 if bit else -1)
                if time<=edges[i+1]:break
            self.assertAlmostEqual(rx.voltage(time*1e-9*2.5e9),.4*float((c@state).item()),places=11)

    def test_wired_shared_rails_preserve_mode_budget_and_clock_ownership(self):
        from baseline_envelope import configured_environment,clock_screen_environment,single_ended_reference_payload_environment,wired_shared_impairment,P
        design=load_design();contract=design.contract
        original=configured_environment(design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8))
        e,report=single_ended_reference_payload_environment(original,dict(link_r_ohm=1e-5),False)
        self.assertIsNotNone(e)
        self.assertAlmostEqual(report['ledger']['total_chip_supply_current_a'],
            original['inventory_current_report']['total_ma']/1000)
        self.assertLess(abs(report['ledger']['power_balance_residual_w']),1e-12)
        impairment=wired_shared_impairment(e)
        self.assertTrue(any(t['frequency_hz']==2.5e9 for t in impairment['rail_tones']))
        # Arbitrary TX phase must not leak into the independent RX aperture.
        changed=dict(e,periodic_clock=None,delivered_phase_tones=[(1e6,100.,0.)])
        self.assertEqual(wired_shared_impairment(changed),impairment)
        with self.assertRaises(ValueError):wired_shared_impairment(dict(e,payload_engine='rf'))

    def test_adc_activity_cannot_borrow_dac_or_reference_allocations(self):
        from copy import deepcopy
        from internal_phase_bound import adc_activity_allocation
        from baseline_envelope import configured_environment,clock_screen_environment,P
        design=load_design();contract=design.contract
        e,_=clock_screen_environment(design,'rf',2.426e9)
        self.assertAlmostEqual(adc_activity_allocation(e),.016)
        from baseline_envelope import partitioned_host_sources
        e['adc_switching']=dict(sample_hz=2.426e9/64,mean_a=.016,
                                pulse_tau_s=.2e-9,harmonics=4)
        self.assertTrue(partitioned_host_sources(e))
        e['adc_switching']['mean_a']=.017
        with self.assertRaisesRegex(ValueError,'own block allocation'):
            partitioned_host_sources(e)
        changed=deepcopy(e)
        blocks=changed['inventory_current_report']['by_block_ma']
        blocks['dac_i']+=100
        blocks['refbuf']+=100
        self.assertEqual(adc_activity_allocation(changed),adc_activity_allocation(e))
        blocks['adc_i']=6
        self.assertAlmostEqual(adc_activity_allocation(changed),.014)
        changed['inventory_current_report']['mode']='rf_tx'
        with self.assertRaises(ValueError):adc_activity_allocation(changed)

    def test_pad_return_uses_the_selected_host_output_load(self):
        from design_definition import Scenario
        from baseline_envelope import configured_environment,clock_screen_environment,pad_ground_tones,P
        from robustness_envelope import host_harmonic_current,shared_return_transfer
        design=load_design();c=design.contract
        config=design.configure(engine='wire',direction='duplex',reference_hz=2.5e9,host_divider=8)
        e=configured_environment(config)
        scenario=Scenario().override(reason='Adverse external host output loading',host_output_load_f=10e-12)
        altered=configured_environment(config,scenario)
        self.assertEqual(altered['design_provenance'],e['design_provenance'])
        self.assertTrue(altered['scenario_overrides'])
        original=pad_ground_tones(e);stress=pad_ground_tones(altered)
        h=e['host_spectrum'];n=e['network'];f=h['d2h_word_hz']/2
        transfer=shared_return_transfer(f,return_r=n['return_r_ohm'],
            return_l=n['return_l_h'],**n['network'])['ground_ohm']
        delta=(host_harmonic_current(f,h['d2h_word_hz'],1,h['d2h_internal_tau_s'],output_cap_f=10e-12)
               -host_harmonic_current(f,h['d2h_word_hz'],1,h['d2h_internal_tau_s'],output_cap_f=h['output_cap_f']))
        self.assertGreater(abs(delta),0)
        self.assertAlmostEqual(abs(stress[f]-original[f]-delta*transfer),0,places=12)

    def test_tx_current_margin_matches_dc_resistance_and_rejects_invalid_baseline(self):
        from internal_phase_bound import tx_current_margin
        from baseline_envelope import configured_environment,clock_screen_environment,P
        design=load_design();contract=design.contract
        e,_=clock_screen_environment(design,'rf',2.426e9)
        opts=contract['physical_services']['external_clock_input']['input_model']
        clock=dict(input_peak_v=0.,input_slope_v_per_s=0.,carrier_amplitude_v=1.,
            leg_bound_v=np.array([.1,.1]),delay_slope=0.)
        result=tx_current_margin(e,[2.501,3.2],opts,clock,frequencies=[1.])
        network=e['network'];resistance=network['network']['feed_r']+network['network']['package_r']+network['return_r_ohm']
        self.assertAlmostEqual(result['minimum_sampled_allowance_a'],.001/resistance,delta=1e-9)
        self.assertEqual(result['cases'][0]['next_boundary_failures'],['rail'])
        failed=tx_current_margin(e,[2.49,3.2],opts,clock,frequencies=[1.])
        self.assertEqual(failed['minimum_sampled_allowance_a'],0.)
        self.assertFalse(failed['cases'][0]['baseline_checks']['rail'])

    def test_normal_mute_is_causal_and_fault_mute_stays_abrupt(self):
        from selected_rf import output_enable_envelope
        launch=1e-6;stop=2e-6
        times=np.array([launch-1e-9,launch,stop-1e-9,stop,stop+10e-9,stop+21e-9])
        normal=output_enable_envelope(times,launch,stop)
        fault=output_enable_envelope(times,launch,stop,fault=True)
        np.testing.assert_array_equal(normal[:3],fault[:3])
        self.assertEqual(normal[0],0.);self.assertEqual(normal[1],0.)
        self.assertGreater(normal[3],.999999)
        self.assertAlmostEqual(normal[4],.5,places=8)
        self.assertEqual(normal[5],0.)
        np.testing.assert_array_equal(fault[3:],np.zeros(3))
        with self.assertRaises(ValueError):output_enable_envelope(times,stop,launch)

    def test_loaded_threshold_edges_against_analytic_sinusoid(self):
        from selected_rf import coupled_load_clock_edges,DeliveredClock
        f=1e9;period=1/f;root=.75*period
        t=np.linspace(0,10*period,101)
        environment=dict(carrier_hz=f,delivered_phase_tones=[],
            periodic_clock=dict(carrier_hz=f,period_s=period,edges_s=np.array([root])),
            reference_threshold=dict(carrier_v=.2+0j,input_tones=[],downstream_delay_tones=[],
                threshold_v=0.,input_edges_s=np.array([root]),period_s=period))
        response=dict(times_s=t,input_v=np.full_like(t,.01),delay_s=np.full_like(t,2e-12),resolved_offset_hz=5e9)
        edges,report=coupled_load_clock_edges(environment,response)
        interior=(edges['indices']>=2)&(edges['indices']<=7)
        expected=(edges['indices'][interior]+1-np.arccos(-.01/.2)/(2*np.pi))*period+2e-12
        np.testing.assert_allclose(edges['edges_s'][interior],expected,atol=1e-18,rtol=0.)
        clock=DeliveredClock(dict(environment,local_load_response=response))
        actual=edges['edges_s'][interior]
        np.testing.assert_allclose(clock.phase(actual)+2*np.pi*f*actual,2*np.pi*edges['indices'][interior],atol=1e-12)
        self.assertLess(report['maximum_root_residual_v'],1e-10)
        settled=dict(response,background=dict(input_v=.01,delay_s=2e-12))
        clock=DeliveredClock(dict(environment,local_load_response=settled))
        cycles=np.array([-100.,100.])
        roots=(cycles+1-np.arccos(-.01/.2)/(2*np.pi))*period+2e-12
        np.testing.assert_allclose(clock.phase(roots)+2*np.pi*f*roots,2*np.pi*cycles,atol=1e-12)

        with self.assertRaises(ValueError):
            coupled_load_clock_edges(environment,dict(response,input_v=np.full_like(t,.19)))

    def test_converter_load_transfer_matches_independent_five_node_solution(self):
        from converter_dynamics import coupled_reference_load_transfer,local_impedance
        from baseline_envelope import reference_input_solution,network_cases
        frequencies=np.geomspace(1e3,1e10,51)
        for _,ret,esl in network_cases(load_design()):
            candidate=shared_board_candidate()
            candidate['return_l_h']=ret
            candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=esl)
            ports=coupled_reference_load_transfer(frequencies,candidate)
            for i,f in enumerate(frequencies):
                independent=reference_input_solution(f,candidate,[0,-1,0,1,0],return_options=dict(link_r_ohm=1e-5))
                v=independent['network_voltage']
                for key,expected in [('rail_v_per_a',v[1]-v[3]),('return_v_per_a',v[3]),('input_v_per_a',independent['local_input_v'])]:
                    np.testing.assert_allclose(ports[key][i],expected,rtol=1e-7,atol=1e-9)
            dc=coupled_reference_load_transfer([0.],candidate)
            self.assertAlmostEqual(dc['input_v_per_a'][0].real,-dc['return_v_per_a'][0].real)
            unloaded=coupled_reference_load_transfer(frequencies,candidate,cap_f=0.,link_r_ohm=1e-12)
            np.testing.assert_allclose(unloaded['rail_v_per_a'],local_impedance(frequencies,candidate),rtol=1e-9,atol=1e-10)
        from selected_rf import DeliveredClock
        with self.assertRaisesRegex(ValueError,'threshold-event migration'):
            DeliveredClock(dict(local_load_response=dict(input_v=[0.])))

    def test_differential_reference_load_against_seven_node_solution(self):
        from reference_input_probe import check_network
        from unittest.mock import patch
        design=load_design()
        with patch('reference_input_probe.load_design',side_effect=AssertionError('Unexpected design reload')):
            checked=check_network(design=design)
        self.assertEqual(checked['design_provenance'],design.provenance())
        self.assertEqual(checked['load_transfer_points'],1404)
        self.assertLess(checked['maximum_load_transfer_difference_ohm'],1e-7)

    def test_current_ownership_and_independent_resistive_node_solution(self):
        c=shared_board_candidate();n=c['network']
        for mode,wire_current,total in [('rf',None,.240),('wire',None,.292),('wire',.050,.246)]:
            r=selected_dc_ledger(mode,c,wire_current_a=wire_current)
            self.assertAlmostEqual(r['total_chip_supply_current_a'],total)
            self.assertAlmostEqual(r['host_node_current_a']+r['h2d_internal_current_within_host_a'],.110)
            self.assertEqual(r['owner_current_a']['timing'],.044)
            gs=1/n['feed_r'];gp=1/n['package_r'];gg=1/c['return_r_ohm']
            vb,vd,vg=np.linalg.solve([[gs+gp,-gp,0],[-gp,gp,0],[0,0,gg]],
                [gs*3.3-r['host_node_current_a'],-r['local_branch_current_a'],total])
            self.assertAlmostEqual(vd-vg,r['local_payload_clock_core_rail_v'])
            self.assertAlmostEqual(vb-vg,r['host_rail_v'])
            self.assertLess(abs(r['power_balance_residual_w']),1e-12)
            self.assertAlmostEqual(sum(r['owner_current_a'].values()),total)
        with self.assertRaises(ValueError):selected_dc_ledger('rf',c,h2d_internal_a=.111)
        with self.assertRaises(ValueError):selected_dc_ledger('rf',c,wire_current_a=.05)
        with self.assertRaises(ValueError):selected_dc_ledger('wire',c,wire_current_a=.097)

    def test_adc_switching_spectrum_matches_time_domain_charge(self):
        from converter_dynamics import SARParameters,adc_switching_sources
        p=SARParameters();rate=37.5e6;mean=.017;tau=.2e-9;origin=.4e-9
        duration=np.asarray(p.bit_durations_s);starts=np.r_[0.,np.cumsum(duration[:-1])]
        events=np.r_[-p.acquisition_s,starts,starts+duration-p.comparator_s,sum(duration)]+origin
        period=1/rate;times=(np.arange(32768)+.5)*period/32768
        current=np.zeros(len(times));charge=mean*period/len(events)
        for event in events%period:
            for wrap in (0,1):
                elapsed=times-event+wrap*period
                positive=np.maximum(elapsed,0.)
                current+=np.where(elapsed>=0,charge*positive**2*np.exp(-positive/tau)/(2*tau**3),0.)
        self.assertAlmostEqual(float(np.mean(current)),mean,places=9)
        spectrum=adc_switching_sources(sample_hz=rate,mean_a=mean,pulse_tau_s=tau,origin_s=origin)
        for harmonic in (1,5,20):
            observed=2*np.mean(current*np.exp(-2j*np.pi*harmonic*rate*times))
            np.testing.assert_allclose(observed,-spectrum[harmonic*rate][1],rtol=1e-6,atol=1e-10)
            self.assertAlmostEqual(abs(sum(spectrum[harmonic*rate])),0.)
        with self.assertRaises(ValueError):
            adc_switching_sources(sample_hz=1e9,mean_a=mean,pulse_tau_s=tau)

    def test_capped_rail_grid_retains_extrema_enclosure(self):
        tones=[dict(frequency_hz=1e6,clock_rail_voltage_peak_v=.1,voltage_phase_rad=.31)]
        r=rail_excursion(tones,dc_v=3.,samples_per_fastest_period=2**22)
        self.assertTrue(r['grid_capped'])
        self.assertEqual(r['samples'],2**20)
        self.assertEqual(r['requested_samples'],2**22)
        self.assertLessEqual(r['enclosed_interval_v'][0],2.9)
        self.assertGreaterEqual(r['enclosed_interval_v'][1],3.1)

    def test_coherent_enclosure_contains_known_sinusoid_extrema(self):
        t=[dict(frequency_hz=1e6,clock_rail_voltage_peak_v=.1,voltage_phase_rad=.31)]
        for resolution in (8,16,32):
            r=rail_excursion(t,dc_v=3.,samples_per_fastest_period=resolution)
            self.assertLessEqual(r['enclosed_interval_v'][0],2.9)
            self.assertGreaterEqual(r['enclosed_interval_v'][1],3.1)
            self.assertGreaterEqual(r['sampled_interval_v'][0],2.9)
            self.assertLessEqual(r['sampled_interval_v'][1],3.1)
        cancel=t+[dict(t[0],voltage_phase_rad=.31+np.pi)]
        r=rail_excursion(cancel,dc_v=3.)
        np.testing.assert_allclose(r['sampled_interval_v'],[3.,3.],atol=1e-12)


class ComparatorDeadlineTests(unittest.TestCase):
    def test_asynchronous_timing_preserves_reference_state_across_chunks(self):
        from converter_dynamics import paired_sar
        time=(np.arange(32)+1)*25.6e-9
        values=.65*np.exp(2j*np.pi*9.7e6*time)
        ref=lambda t:1.+.005*np.sin(2*np.pi*25e6*t)
        rail=lambda t:3.+.05*np.cos(2*np.pi*13e6*t)
        comparator=dict(tau_s=75e-12,launch_s=.1e-9,output_threshold_v=.2)
        def run(a,b,state=None,model=comparator):
            return paired_sar(values[a:b],values[a:b],time[a:b],ref,rail,
                comparator_model=model,initial_state=state)
        words,report,trace=run(0,32)
        w1,r1,t1=run(0,16)
        w2,r2,t2=run(16,32,t1['final_state'])
        np.testing.assert_array_equal(words,np.vstack((w1,w2)))
        np.testing.assert_allclose(trace['conversion_windows_s'],
            np.vstack((t1['conversion_windows_s'],t2['conversion_windows_s'])),rtol=0,atol=1e-20)
        self.assertAlmostEqual(trace['final_state']['reference_v'],t2['final_state']['reference_v'],places=13)
        self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-20)
        self.assertGreater(report['comparator_decision_interval_s'][1],.5e-9)
        self.assertGreater(report['actual_completion_margin_s'],0.)
        with self.assertRaisesRegex(ValueError,'conversion deadline'):
            run(0,32,model=dict(comparator,tau_s=1e-9))
        with self.assertRaisesRegex(ValueError,'Compatible SAR'):
            run(16,32,t1['final_state'],model=None)

    def test_regeneration_deadline_distinguishes_zero_and_small_overdrive(self):
        from converter_dynamics import comparator_deadline_screen
        margins=np.full((2,10,2),.1)
        margins[0,0,0]=0.
        margins[1,9,1]=-.001
        result=comparator_deadline_screen(margins,decision_s=.5e-9)
        self.assertEqual([x['unresolved_decisions'] for x in result['cases']],[1,1,1,2])
        self.assertEqual(result['cases'][-1]['unresolved_by_bit_msb_first'],[1]+[0]*8+[1])
        slower=comparator_deadline_screen(margins,decision_s=1e-9)
        self.assertEqual(slower['cases'][-1]['unresolved_decisions'],1)
        json.dumps(result,allow_nan=False)
        with self.assertRaises(ValueError):
            comparator_deadline_screen(margins,decision_s=.1e-9)


class WiredSupplyObservationTests(unittest.TestCase):
    def test_samples_before_source_onset_remain_in_diagnostic_history(self):
        from wired_envelope import physical_receiver
        impairment=dict(jitter_rms_s=0.,jitter_hz=1e6,noise_rms_v=0.,offset_v=0.)
        for edges in (None,np.arange(41)/2.5e9+1e-9):
            receiver=physical_receiver([0,1]*20,2.5e9,.35,0.,100e-12,2.7e-12,
                impairment,source_edges_s=edges)
            self.assertEqual(receiver.voltage(-.2),0.)
            self.assertEqual(receiver.sample_observations[0],(-.2,-.2,0.,0.))
            if edges is not None:
                self.assertEqual(receiver.voltage(.2),0.)
                self.assertEqual(receiver.sample_observations[0],(.2,.2,0.,0.))

    def test_gap_audit_checks_interior_drift_and_actual_aperture(self):
        from wired_envelope import gap_phase_audit
        observations=[dict(bit_index=i,transition=i in (0,4),qualified=True,
                           holdover_phase_bound_ui=.1) for i in range(5)]
        trace=[0.,1.1,2.2,3.1,4.]
        result=gap_phase_audit(observations,trace,rate=1.)
        self.assertAlmostEqual(result['peak_bound_ui'],.3)
        self.assertEqual(result['samples_outside_quarter_ui'],1)
        attributed=gap_phase_audit(observations,trace,rate=1.,
            nominal_sample_ui=list(range(5)),scored_start_bit=3)
        peak=attributed['peak_sample']
        self.assertEqual(peak['bit_index'],2)
        self.assertAlmostEqual(peak['aperture_change_ui'],.2)
        self.assertAlmostEqual(peak['nominal_clock_drift_ui'],0.)
        self.assertAlmostEqual(sum(peak[k] for k in ('nominal_clock_drift_ui',
            'aperture_change_ui','source_phase_warp_ui')),peak['signed_drift_ui'])
        self.assertEqual(attributed['scored_samples_outside_quarter_ui'],0)
        self.assertAlmostEqual(attributed['scored_peak_bound_ui'],.2)
        # A source with the same phase trajectory removes the apparent drift.
        matched=gap_phase_audit(observations,trace,rate=1.,source_edges_s=trace)
        self.assertAlmostEqual(matched['peak_bound_ui'],.1)
        self.assertEqual(matched['samples_outside_quarter_ui'],0)
        with self.assertRaises(ValueError):gap_phase_audit(observations,trace[:-1],rate=1.)

    def test_tracking_uses_eye_budget_and_reacquires_after_excess_error(self):
        from wired_envelope import physical_receiver
        bits=[0,1]*1300
        for step,should_lose in ((.13,False),(.32,True)):
            edges=np.arange(len(bits)+1)/2.5e9
            edges[1400:]+=step/2.5e9
            receiver=physical_receiver(bits,2.5e9,0.,0.,50e-12,1e-12,
                dict(jitter_rms_s=0.,jitter_hz=1e6,noise_rms_v=0.,offset_v=0.),
                source_edges_s=edges)
            receiver.detector_noise_rms_s=0.
            observations=[];receiver.timing_observer=observations.append
            for word in range(240):receiver.forecast(word);receiver.consume(word)
            self.assertTrue(all(x['qualified'] for x in observations[1200:1390]))
            near=observations[1390:1500]
            self.assertEqual(any(not x['qualified'] for x in near),should_lose)
            if not should_lose:
                self.assertGreater(max(x['detector_history_peak_ui'] for x in near),.1)
                self.assertTrue(all(x['holdover_phase_bound_ui']<.25 for x in near))
            self.assertTrue(all(x['qualified'] for x in observations[2200:]))

    def test_timing_observations_are_committed_not_forecast(self):
        from behavioral import RecoveredWordSource
        receiver=RecoveredWordSource([0,1]*50,2.5e9,.35,100.)
        observations=[]
        receiver.timing_observer=observations.append
        receiver.forecast(0)
        self.assertEqual(observations,[])
        receiver.consume(0)
        self.assertEqual([x['bit_index'] for x in observations],list(range(10)))
        receiver.forecast(1)
        self.assertEqual(len(observations),10)
        receiver.consume(1)
        self.assertEqual(len(observations),20)
        self.assertTrue(all(b['time_s']>a['time_s'] for a,b in zip(observations,observations[1:])))
        self.assertTrue(any(x['transition'] for x in observations))

    def test_extended_window_keeps_fixed_training_and_scores_tail(self):
        from wired_envelope import causal_receiver_envelope
        bits=np.random.default_rng(17).integers(0,2,3010).tolist()
        result=causal_receiver_envelope(source_bits=bits,
            channel_cases=((2.7e-12,100e-12),),initial_conditions=((.35,100.),))
        self.assertEqual(len(result['cases']),1)
        self.assertEqual(result['cases'][0]['heldout_bits'],1610)
        json.dumps(result,allow_nan=False)
        self.assertTrue(np.isfinite(result['cases'][0]['final_frequency_correction_ppm']))

    def test_voltage_validity_survives_forecast_snapshots(self):
        from wired_envelope import causal_receiver_envelope
        scenarios=[dict(name='low_constant_rail',delay_tones=[],signal_scale=2.4/3.3,
                        rail_dc_v=2.4,rail_tones=[]),
                   dict(name='valid_constant_rail',delay_tones=[],signal_scale=3./3.3,
                        rail_dc_v=3.,rail_tones=[])]
        result=causal_receiver_envelope(timing_scenarios=scenarios,channel_cases=((2.7e-12,100e-12),))
        for r in result['cases']:
            low=r['impairment']['name']=='low_constant_rail'
            self.assertEqual(r['observed_rail_interval_v'],[2.4,2.4] if low else [3.,3.])
            self.assertEqual(r['rail_observations_outside_legacy_fixture']>0,low)


class HSPadReturnTests(unittest.TestCase):
    def test_primitive_transfer_never_loads_the_current_design(self):
        from unittest.mock import patch
        from baseline_envelope import hs_pad_transfer
        from protocol_pad import SharedWiredPad
        with patch('baseline_envelope.load_design',side_effect=AssertionError('Unexpected design reload')):
            primitive=hs_pad_transfer(1e9)
            explicit=hs_pad_transfer(1e9,capacitance_f=SharedWiredPad().C)
        for key in primitive:
            np.testing.assert_allclose(primitive[key],explicit[key],rtol=0.,atol=0.)

    def test_loaded_ground_matches_independent_seven_node_network(self):
        from baseline_envelope import hs_pad_transfer
        from protocol_pad import SharedWiredPad
        from robustness_envelope import shared_return_transfer
        n=shared_board_candidate();r=n['network'];rg=n['return_r_ohm'];lg=n['return_l_h']
        for f in (156.25e6,1.875e9):
            w=2*np.pi*f
            ys=1/(r['feed_r']+1j*w*r['feed_l']);yp=1/(r['package_r']+1j*w*r['package_l'])
            yg=1/(rg+1j*w*lg)
            yd=1/(r.get('die_esr',0.)+1j*w*r.get('die_esl',0.)+1/(1j*w*r['die_c']))
            yb=1/(r['board_esr']+1j*w*r['board_esl']+1/(1j*w*r['board_c']))
            m=np.zeros((7,7),complex)
            m[:3,:3]=[[ys+yb+yp,-yp,0],[-yp,yp+yd,-yd],[0,-yd,yg+yd]]
            local=1j*w*SharedWiredPad().C+np.diag([1/42.75,1/47.25])
            m[3:5,3:5]+=local
            m[3:5,2]-=local@np.ones(2);m[2,3:5]-=np.ones(2)@local
            m[2,2]+=np.ones(2)@local@np.ones(2)
            for leg,l in enumerate((1.6e-9,2.4e-9)):
                y=1/(.2+1j*w*l);a,b=3+leg,5+leg
                m[a,a]+=y;m[b,b]+=y+1/45.;m[a,b]-=y;m[b,a]-=y
            source=np.zeros(7);source[2]=1.
            v=np.linalg.solve(m,source)
            z=shared_return_transfer(f,return_r=rg,return_l=lg,injection_weights=(0.,0.,1.),**r)
            h=hs_pad_transfer(f,termination_ohm=(42.75,47.25),bond_l_h=(1.6e-9,2.4e-9))
            g=z['ground_ohm']/(1+z['ground_ohm']*sum(h['ground_board'])/45.)
            np.testing.assert_allclose(v[2],g,rtol=1e-13)
            np.testing.assert_allclose(v[5:],h['ground_board']*g,rtol=1e-13)
            self.assertLess(max(abs(m@v-source)),1e-13)
        with self.assertRaises(ValueError):hs_pad_transfer(1e6,bond_l_h=(-1.,0.))

    def test_dc_return_current_is_redirected_not_added_to_budget(self):
        from baseline_envelope import usb_supply_environment,usb_hs_output
        e,_=usb_supply_environment(load_design())
        ledger=e['ledger']
        for node in (None,0,1):
            r=usb_hs_output(e,ledger,drive_node=node)
            board=np.array(r['board_dc_v']);g=r['loaded_dc_ground_v']
            self.assertAlmostEqual(g/e['network']['return_r_ohm']+sum(board)/45.,sum(e['inventory_current_a'].values()),places=12)
            current=np.zeros(2)
            if node is not None:current[node]=e['wired_usb_parameters']['drive_current_a']
            die=np.array(r['die_local_dc_v'])+g
            np.testing.assert_allclose((die-g)/e['wired_usb_parameters']['termination_ohm_per_leg']+(die-board)/.2,current,atol=1e-14)
            np.testing.assert_allclose((die-board)/.2,board/45.,atol=1e-14)
            self.assertTrue(r['quiet_pin_dc_within_20mv'])
            lo,hi=r['differential']['sampled_interval_v']
            self.assertAlmostEqual(lo,hi,places=12)
            self.assertGreater(r['quiet_pin_observed_abs_peak_v'],.02)


class HostRateTradeoffTests(unittest.TestCase):
    def test_rate_comparison_preserves_bandwidth_current_ownership_and_latency(self):
        from baseline_envelope import usb_hs_level_campaign,network_cases
        from rf_quality_budget import current_allocation
        design=load_design()
        r=usb_hs_level_campaign(design.contract,design=design)
        budget=current_allocation(design.architecture,'usb')
        self.assertEqual({x['network_case'] for x in r['host_rate_controls']},{x[0] for x in network_cases(design)})
        for c in r['host_rate_controls']:
            word=c['word_hz'];dc=c['ledger']
            self.assertGreaterEqual(c['d2h_harmonics']*word/2,1.875e9)
            self.assertGreaterEqual(c['h2d_harmonics']*word/2,937.5e6)
            self.assertAlmostEqual(dc['total_chip_supply_current_a'],budget['total_ma']/1000)
            self.assertAlmostEqual(dc['host_node_current_a']+dc['h2d_internal_current_within_host_a'],budget['by_rail_ma']['host']/1000)
            for t in c['transport']:
                # Independent accounting of six frame traversals, four queue
                # words and three H0 cycles; fixed analog, FPGA and packing.
                expected=(6*t['frame_words']+4+24)/word+40e-9+34e-9+20/480e6
                self.assertAlmostEqual(t['incomplete_roundtrip_bound_s'],expected,places=18)
                self.assertAlmostEqual(t['payload_capacity_bps'],(t['frame_words']-5)*10*word/t['frame_words'])
        # Historical-rate interventions must not pretend to be the selected
        # host configuration. Their harmonic coverage also differs from nominal.
        host_hz=design.architecture['direct_stream_service']['budget']['host_hz']
        for c in r['host_rate_controls']:
            self.assertEqual(c['diagnostic_intervention']['host_word_hz'],c['word_hz'])
            self.assertEqual(c['resolved_configuration']['host_input_hz'],host_hz)
            self.assertEqual(c['design_provenance']['design_fingerprint'],design.fingerprint)


class PartitionedReturnTests(unittest.TestCase):
    def test_shorting_returns_recovers_original_three_node_network(self):
        from baseline_envelope import partitioned_return_solution,clock_screen_environment,P
        from robustness_envelope import shared_return_transfer
        e,_=clock_screen_environment(load_design(),'wire',2.5e9);n=e['network']
        for f in (156.25e6,1.875e9):
            for old,new in (((-1.,0.,1.),(-1.,0.,1.,0.,0.)),((0.,-1.,1.),(0.,-1.,1.,0.,0.)),((0.,0.,1.),(0.,0.,0.,1.,0.))):
                reference=shared_return_transfer(f,return_r=n['return_r_ohm'],return_l=n['return_l_h'],injection_weights=old,**n['network'])
                result=partitioned_return_solution(f,n,new,link_r_ohm=1e-7)
                v=result['voltage']
                np.testing.assert_allclose([v[0],v[1],v[3]],
                    [reference['board_ohm'],reference['die_ohm'],reference['ground_ohm']],rtol=2e-6,atol=1e-7)
                self.assertLess(result['kcl_residual_a'],1e-8)

    def test_dc_series_paths_and_current_relocation(self):
        from baseline_envelope import partitioned_return_solution,clock_screen_environment,P
        e,_=clock_screen_environment(load_design(),'wire',2.5e9);n=e['network'];c=.1
        rg=n['return_r_ohm'];rf=n['network']['feed_r'];rp=n['network']['package_r']
        # Independent DC injection example; these currents are not chip budgets.
        for input_at_feed in (False,True):
            host_feed=.110 if input_at_feed else .110-.0240625;local=.246-host_feed
            source=[3.3/rf-host_feed,-local,.110,.136,0.]
            for fraction in (0.,.25,.5,.75):
                result=partitioned_return_solution(0.,n,source,host_cap_fraction=fraction)
                vb=3.3-rf*.246;common=c*rg*.246
                expected=[vb,vb-rp*local,common+2*(1-c)*rg*.110,
                    common+2*(1-c)*rg*.136,common]
                np.testing.assert_allclose(result['voltage'],expected,rtol=1e-12,atol=1e-14)
                self.assertAlmostEqual((3.3-result['voltage'][0].real)/rf,.246,places=12)

    def test_passive_power_balance_with_capacitive_and_conductive_coupling(self):
        from baseline_envelope import partitioned_return_solution,clock_screen_environment,hs_pad_transfer,P
        e,_=clock_screen_environment(load_design(),'wire',2.5e9);n=e['network']
        for fraction in (0.,.25,.5,.75):
            for link in (None,1.):
                for f in (156.25e6,1.875e9):
                    load=sum(hs_pad_transfer(f,capacitance_f=e['wired_pad_capacitance_f'])['ground_board'])/45.
                    r=partitioned_return_solution(f,n,[-.01+.02j,-.03,.04-.01j,.01j,0.],
                        host_cap_fraction=fraction,link_r_ohm=link,quiet_load_s=load)
                    self.assertLess(r['kcl_residual_a'],1e-12)
                    self.assertLess(abs(r['power_residual_w']),1e-12)
        with self.assertRaises(ValueError):partitioned_return_solution(1e6,n,[0]*5,coupling_f=-1.)
        with self.assertRaises(ValueError):partitioned_return_solution(1e6,n,[0]*5,host_cap_fraction=1.)


class ReferenceReturnTests(unittest.TestCase):
    def test_loaded_input_matches_series_thevenin_and_power_balance(self):
        from baseline_envelope import clock_screen_environment,partitioned_return_solution,reference_input_solution,P
        e,_=clock_screen_environment(load_design(),'rf',2.484e9);n=e['network']
        for options in (dict(link_r_ohm=1e-5),dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=.2)):
            for f in (156.25e6,2.484e9):
                z=partitioned_return_solution(f,n,[0,0,0,1,0],**options)['voltage'][3]
                w=2*np.pi*f;zc=1/(1j*w*3e-12);zs=50.2+1j*w*2e-9
                for source,injection in ((.5,[0]*5),(0.,[-.02,0,.02,0,0])):
                    unloaded=partitioned_return_solution(f,n,injection,**options)['voltage']
                    current=(source-unloaded[3])/(zs+zc+z)
                    r=reference_input_solution(f,n,injection,source_v=source,return_options=options)
                    np.testing.assert_allclose(r['input_return_current_a'],current,rtol=2e-8,atol=1e-12)
                    np.testing.assert_allclose(r['local_input_v'],zc*current,rtol=2e-8,atol=1e-12)
                    np.testing.assert_allclose((r['pad_board_v']-source)/zs+r['local_input_v']/zc,0.,atol=1e-12)
                    if source:
                        independent_loss=(50.2+z.real)*abs(current)**2/2
                        self.assertAlmostEqual(r['source_real_power_w'],independent_loss,places=10)

    def test_exact_coherent_phasor_shift_and_missing_multiple_edges(self):
        from baseline_envelope import reference_edge_screen
        f=2e9;carrier=.2;perturb=.04j;threshold=.02
        r=reference_edge_screen(f,carrier,[(f,perturb)],threshold_v=threshold)
        total=carrier+perturb
        expected=(np.arcsin(threshold/abs(total))-np.angle(total)-np.arcsin(threshold/carrier))/(2*np.pi*f)
        self.assertAlmostEqual(r['static_mean_edge_shift_ps'],expected*1e12,places=7)
        self.assertEqual(r['unique_edge_windows'],1)
        self.assertLess(r['maximum_root_voltage_residual_v'],1e-9)
        missing=reference_edge_screen(f,carrier,[(f,-carrier)])
        self.assertEqual(missing['missing_rising_edge_windows'],1)
        self.assertIsNone(missing['centered_edge_error_rms_ps'])
        multiple=reference_edge_screen(f,carrier,[(2*f,.4)],substeps=64)
        self.assertEqual(multiple['multiple_rising_edge_windows'],1)
        self.assertFalse(multiple['all_windows_have_one_rising_edge'])

    def test_correlated_downstream_delay_cancels_in_small_signal_limit(self):
        from baseline_envelope import reference_edge_screen
        f=2e9;a=.2;threshold=.02;v=1e-5;offset=f/16
        slope=2*np.pi*f*np.sqrt(a*a-threshold*threshold)
        r=reference_edge_screen(f,a,[(offset,v)],threshold_v=threshold,
            downstream_delay_tones=[(offset,v/slope)])
        self.assertGreater(r['centered_edge_error_rms_ps'],.002)
        self.assertLess(r['combined_edge_error_rms_ps'],r['centered_edge_error_rms_ps']/1000)
        self.assertTrue(r['output_clock_order_preserved'])
        refined=reference_edge_screen(f,a,[(offset,v)],threshold_v=threshold,substeps=64,
            downstream_delay_tones=[(offset,v/slope)])
        self.assertAlmostEqual(r['centered_edge_error_rms_ps'],refined['centered_edge_error_rms_ps'],places=8)
        with self.assertRaises(ValueError):reference_edge_screen(f,a,[(offset,complex(float('nan'),0))])


class PeriodicClockConsumerTests(unittest.TestCase):
    def test_phase_and_divider_crossings_follow_edges_across_period_boundaries(self):
        from selected_rf import DeliveredClock,PeriodicEdgePhase
        carrier=1e9;n=32;k=np.arange(n)
        edges=(k+.17+.03*np.cos(2*np.pi*k/8))/carrier
        record=dict(carrier_hz=carrier,period_s=n/carrier,edges_s=edges)
        environment=dict(carrier_hz=carrier,delivered_phase_tones=(),periodic_clock=record)
        clock=DeliveredClock(environment);indices=np.arange(-64,129)
        ideal=indices/carrier
        expected=edges[indices % n]+(indices//n)*n/carrier
        actual=ideal+clock.crossing_error(ideal,carrier)
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-20)
        np.testing.assert_allclose(clock.phase(expected)+2*np.pi*carrier*expected,2*np.pi*indices,atol=1e-11)
        query=np.linspace(-2e-9,60e-9,100)
        np.testing.assert_allclose(clock.phase(query),clock.phase(query+n/carrier),atol=1e-12)
        noisy=DeliveredClock(dict(environment,delivered_phase_tones=((carrier/7,.01,.3),)))
        error=noisy.crossing_error(ideal,carrier)
        self.assertLess(max(abs(error+noisy.phase(ideal+error)/(2*np.pi*carrier))),1e-16)
        with self.assertRaises(ValueError):PeriodicEdgePhase(dict(record,edges_s=edges[:-1]))
        with self.assertRaises(ValueError):PeriodicEdgePhase(dict(record,edges_s=edges[::-1]))
        with self.assertRaises(ValueError):clock.crossing_error(ideal,carrier/2)
        environment['periodic_clock']['edges_s'][0]+=1e-10
        inspection=clock.environment
        inspection['periodic_clock']['edges_s'][:]=0.
        np.testing.assert_allclose(ideal+clock.crossing_error(ideal,carrier),expected,rtol=0,atol=1e-20)
        response=dict(times_s=np.array([-1e-6,1e-6]),delay_s=np.array([2e-12,2e-12]))
        supplied=dict(carrier_hz=carrier,delivered_phase_tones=(),local_load_response=response)
        held=DeliveredClock(supplied)
        supplied['carrier_hz']=2*carrier
        response['delay_s'][:]=9e-12
        held.environment['local_load_response']['delay_s'][:]=20e-12
        np.testing.assert_allclose(held.crossing_error(np.arange(3)/carrier,carrier),2e-12,rtol=0,atol=1e-20)

    def test_coupled_environment_balances_power_and_rejects_broken_clock(self):
        from baseline_envelope import clock_screen_environment,single_ended_reference_payload_environment
        from design_definition import Scenario
        design=load_design();contract=design.contract
        e,_=clock_screen_environment(design,'rf',2.4e9)
        # Explicit single-ended diagnostic topology, not selected differential hardware.
        _,nominal=single_ended_reference_payload_environment(e,dict(link_r_ohm=1e-5),False)
        stronger,large=single_ended_reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=1.)
        self.assertIsNotNone(stronger)
        self.assertAlmostEqual(large['receiver_carrier_peak_v']/nominal['receiver_carrier_peak_v'],2.)
        self.assertAlmostEqual(large['source_carrier_return_peak_a']/nominal['source_carrier_return_peak_a'],2.)
        self.assertAlmostEqual(large['source_carrier_real_power_w']/nominal['source_carrier_real_power_w'],4.)
        rejected,report=single_ended_reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=2.)
        self.assertIsNone(rejected)
        self.assertEqual(report['status'],'clock_not_accepted_for_payload')
        for invalid in (0.,-1.,float('nan')):
            with self.assertRaises(ValueError):
                single_ended_reference_payload_environment(e,dict(link_r_ohm=1e-5),False,source_peak_v=invalid)
        for options,move in ((dict(link_r_ohm=1e-5),False),(dict(host_cap_fraction=.5,coupling_f=2e-12,host_return_share=.2),True)):
            trial,r=single_ended_reference_payload_environment(e,options,move)
            self.assertIsNotNone(trial)
            self.assertLess(abs(r['ledger']['power_balance_residual_w']),1e-12)
            self.assertAlmostEqual(r['ledger']['total_chip_supply_current_a'],
                e['inventory_current_report']['total_ma']/1000)
            self.assertEqual(trial['phase_components']['supply'],())
            self.assertEqual(trial['rail_maximum_offset_hz'],2.4e9)
            self.assertEqual(len(trial['periodic_clock']['edges_s']),r['resolved_crossings']['carrier_cycles'])
        scenario=Scenario().override(reason='Adverse package clock rejection fixture',
            package_return_inductance_h=2e-9,die_decoupling_esl_h=1e-9)
        bad,_=clock_screen_environment(design,'rf',2.4e9,scenario=scenario)
        trial,r=single_ended_reference_payload_environment(bad,dict(link_r_ohm=1e-5),False)
        self.assertIsNone(trial)
        self.assertEqual(r['status'],'clock_not_accepted_for_payload')


class SelectedRFTests(unittest.TestCase):
    def test_scalar_tx_observer_cannot_equalize_frequency_shape(self):
        from scipy import signal
        from selected_rf import he_source,he_scalar_observation
        wave,_=he_source(oversample=1)
        cp=wave.metadata['cp'];frames=np.asarray(wave.samples).reshape(-1,256+cp)
        frequency=np.fft.fftfreq(256,1/20e6)
        b,a=signal.butter(5,2*np.pi*10e6,analog=True)
        _,instrument=signal.freqs(b,a,2*np.pi*frequency)
        def capture(shape):
            spectrum=np.fft.fft(frames[:,cp:],axis=1)*instrument*shape
            spectrum*=.3*np.exp(.2j-2j*np.pi*frequency*37e-9)
            data=np.fft.ifft(spectrum,axis=1)
            return np.c_[data[:,-cp:],data].ravel()
        clean=he_scalar_observation(wave,capture(np.ones(256)),observer_cutoff_hz=10e6)
        shaped=he_scalar_observation(wave,capture(1+.3*frequency/10e6),observer_cutoff_hz=10e6)
        self.assertLess(clean['evm_rms'],1e-7)
        self.assertAlmostEqual(clean['fitted_delay_s']/1e-9,37.,places=5)
        self.assertGreater(shaped['evm_rms'],.1)
        self.assertFalse(shaped['per_tone_equalization'])
        self.assertEqual(shaped['evaluated_symbols'],10)

    def test_uniform_rail_fft_matches_direct_tones_with_dc_nyquist_and_aliases(self):
        from selected_rf import rail_at,rail_on_uniform_grid
        for fs in (64e6,63.5e6):
            environment=dict(ledger=dict(local_payload_clock_core_rail_v=3.),
                host_spectrum=dict(tones=[dict(frequency_hz=f,clock_rail_voltage_peak_v=.1,voltage_phase_rad=.3)
                    for f in (1e6,31.75e6,32e6,64e6,65e6)]))
            times=np.arange(901)/fs
            np.testing.assert_allclose(rail_on_uniform_grid(environment,len(times),fs),rail_at(environment,times),rtol=0,atol=1e-11)
            for start in (-1.37e-6,350.123e-6):
                np.testing.assert_allclose(rail_on_uniform_grid(environment,len(times),fs,start_s=start),rail_at(environment,start+times),rtol=0,atol=1e-10)

    def test_receiver_noise_interventions_preserve_legacy_all_off_control(self):
        from baseline_envelope import configured_environment
        from selected_rf import wideband_receive
        design=load_design()
        changes={f'blocks.{name}.parameters.gain_db':design.architecture['blocks'][name]['parameters']['gain_db']+[54.]
                 for name in ('pga_i','pga_q')}
        hypothetical=design.hypothetical(reason='54 dB noise-intervention fixture; unchanged power/noise is an explicit simplification',changes=changes)
        e=configured_environment(hypothetical.configure(engine='rf',direction='rx',
            reference_hz=2.484e9,sample_divider=64,pga_gain_db=54.))
        a=wideband_receive(e,noise=False,gain_settings_db=(54.,))
        b=wideband_receive(e,disabled_noise_sources=('thermal','converter','aperture'),gain_settings_db=(54.,))
        self.assertEqual(a,b)
        self.assertEqual(a['design_provenance'],hypothetical.provenance())
        self.assertNotEqual(hypothetical.fingerprint,design.fingerprint)
        with self.assertRaises(ValueError):wideband_receive(e,disabled_noise_sources=('unknown',))

    def test_input_phase_refinement_conserves_noise_and_matches_threshold_crossing(self):
        from oscillator_noise import loaded_clock_input_phase,PhaseNoise
        import math
        carrier=2.484e9;omega=2*math.pi*carrier;variances=[]
        for bins in (32,128,512):
            phase,r=loaded_clock_input_phase(carrier,receiver_noise_v=75e-6,
                downstream_stage_rms_s=15e-15,noise_bins=bins,source_peak_v=.75,threshold_v=.002,am_depth=.01)
            am=PhaseNoise(r['phase_components']['am']);additive=PhaseNoise(r['phase_components']['additive'])
            t=np.arange(512)/512e6
            exact=np.arcsin(.002/(r['receiver_peak_v']*(1+.01*np.sin(2*np.pi*1e6*t))))/omega
            exact-=exact.mean()
            np.testing.assert_allclose(-am.phase(t)/omega,exact,atol=1e-25)
            expected=omega**2*(r['receiver_random_time_rms_s']**2+r['downstream_random_time_rms_s']**2)
            self.assertAlmostEqual(additive.variance_rad2/expected,1.,places=12)
            np.testing.assert_allclose(phase.phase(t),am.phase(t)+additive.phase(t),atol=1e-16)
            variances.append(additive.variance_rad2)
        np.testing.assert_allclose(variances,variances[0],rtol=1e-12)
        with self.assertRaises(ValueError):loaded_clock_input_phase(carrier,am_depth=1.)
        with self.assertRaises(ValueError):loaded_clock_input_phase(carrier,noise_bins=0)

    def test_observed_gain_control_matches_native_transfer_with_moving_headroom(self):
        from ble_packet import bounded_gain_conversion
        from selected_rf import native_adc
        source=np.linspace(-.9,.9,401)*(1+1j)
        headroom=np.linspace(.3,.6,len(source));reference=np.linspace(.99,1.01,len(source))
        # Lock gain at unity to compare transfer laws, then separately retain
        # the existing causal/delayed gain-controller tests.
        codes,report=bounded_gain_conversion(source,np.zeros(len(source)),
            initial_gain_db=0.,maximum_gain_db=0.,reference_scale=reference,
            pga_peak_v=headroom,converter_bits=10)
        limited=np.clip(source.real,-headroom,headroom)+1j*np.clip(source.imag,-headroom,headroom)
        words,_=native_adc(limited,reference,noise=False)
        np.testing.assert_array_equal(codes,(words[:,0]+1j*words[:,1])/2048)
        self.assertTrue(report['native_transport_low_two_bits_zero'])
        self.assertGreater(report['pga_clipped_samples'],0)

    def test_native_converter_codes_reference_and_saturation(self):
        from selected_rf import native_adc, native_dac
        # Every native code must survive both directions at non-unit reference.
        values=np.arange(-512,512)/512
        words,report=native_adc((values+1j*values)*.93,.93,noise=False)
        decoded,dac=native_dac(words,.93)
        np.testing.assert_allclose(decoded,(values+1j*values)*.93,atol=1e-15)
        self.assertEqual(report['clipped_components'],0)
        self.assertEqual(dac['saturated_components'],0)
        # Exhaustive 12-bit input ramp: bounded error, monotonicity, no wrap.
        ramp=np.arange(-2048,2048)
        decoded,dac=native_dac(np.column_stack((ramp,ramp)),1.)
        self.assertTrue(np.all(np.diff(decoded.real)>=0))
        self.assertLessEqual(max(abs(decoded.real-ramp/2048)),3/2048)
        self.assertEqual(decoded[-1].real,511/512)
        words,report=native_adc(np.array([-2-2j,2+2j]),1.,noise=False)
        np.testing.assert_array_equal(words,[[-2048,-2048],[2044,2044]])
        self.assertEqual(report['clipped_components'],4)

    def test_analog_modes_against_independent_state_space_zoh(self):
        from scipy import signal
        from selected_rf import analog_filter
        drive=np.random.default_rng(41).normal(size=1200)
        for family,ba in (
            ('rx_finite_zero',signal.ellip(5,1,36.40776933523119,1,analog=True)),
            ('rx_all_pole_control',signal.butter(5,1,analog=True)),
            ('tx_third_order',signal.butter(3,1,analog=True))):
            dt=2*np.pi*9e6/1e9
            # Independent real companion state-space integration, rather than
            # the residue decomposition used by the baseline implementation.
            _,reference,_=signal.lsim(signal.tf2ss(*ba),np.r_[drive,0.],
                np.arange(len(drive)+1)*dt,interp=False)
            modeled=analog_filter(drive,1e9,family=family,cutoff_hz=9e6)
            np.testing.assert_allclose(modeled,reference[1:],atol=1e-10)

    def test_filter_history_bound_and_timer_counterexample(self):
        from scipy import signal,linalg
        from selected_rf import filter_settling_requirement
        for family,ba in (
            ('rx_finite_zero',signal.ellip(5,1,36.40776933523119,1,analog=True)),
            ('rx_all_pole_control',signal.butter(5,1,analog=True)),
            ('tx_third_order',signal.butter(3,1,analog=True))):
            req=filter_settling_requirement(family=family,cutoff_hz=500e3)
            json.dumps(dict(requirement=req,sufficient=req['settling_s']<=20e-6),allow_nan=False)
            A,B,C,D=signal.tf2ss(*ba)
            # Independent real companion-state integration of bounded random
            # prehistory followed by zero forcing; no modal state initialization.
            times=np.arange(10001)*.02
            drive=np.random.default_rng(913).uniform(-1,1,len(times))
            _,_,states=signal.lsim((A,B,C,D),drive,times,interp=False)
            for elapsed in np.linspace(0,2*req['settling_s'],31):
                output=abs((C@linalg.expm(A*2*np.pi*500e3*elapsed)@states[-1]).item())
                bound=sum(np.asarray(req['modal_weights'])*np.exp(-np.asarray(req['decay_per_s'])*elapsed))
                self.assertLessEqual(output,bound+1e-13)
            self.assertLessEqual(req['bound_at_deadline'],req['error_budget'])
            slower=filter_settling_requirement(family=family,cutoff_hz=250e3)
            self.assertAlmostEqual(slower['settling_s'],2*req['settling_s'],places=14)
        A,B,C,D=signal.tf2ss(*signal.ellip(5,1,36.40776933523119,1,analog=True))
        state=np.linalg.solve(1j*np.eye(len(A))-A,B[:,0])
        witness=(C@linalg.expm(A*2*np.pi*500e3*20e-6)@state).item()
        self.assertGreater(abs(witness),.06)  # Real sinusoidal prehistory, selectable phase.
        self.assertGreater(abs(witness),1/1024)
        for value in (0.,-1.,float('nan')):
            with self.assertRaises(ValueError):
                filter_settling_requirement(family='rx_finite_zero',cutoff_hz=value)

    def test_analog_filter_record_continuity(self):
        from selected_rf import analog_filter
        values=np.random.default_rng(472).normal(size=1400)+1j*np.random.default_rng(473).normal(size=1400)
        for family in ('rx_finite_zero','rx_all_pole_control','tx_third_order'):
            for interpolation in ('zoh','linear'):
                options=dict(family=family,cutoff_hz=500e3,interpolation=interpolation)
                full=analog_filter(values,20e6,**options)
                state={};first=analog_filter(values[:600],20e6,state_capture=state,**options)
                saved=json.loads(json.dumps(state))
                overlap=1 if interpolation=='linear' else 0
                second=analog_filter(values[600-overlap:],20e6,initial_state=saved,**options)
                np.testing.assert_allclose(np.r_[first,second[overlap:]],full,atol=1e-12)
                reset=analog_filter(values[600-overlap:],20e6,**options)
                self.assertGreater(max(abs(second-reset)),1e-3)
                with self.assertRaises(ValueError):
                    analog_filter(values,20e6,initial_state=saved,**dict(options,cutoff_hz=600e3))

    def test_finite_integrator_filter_against_companion_realization(self):
        from scipy import signal
        from numpy.polynomial import Polynomial
        from selected_rf import analog_filter,analog_modes,filter_settling_requirement
        b,a=signal.ellip(5,1,36.40776933523119,1,analog=True)
        q=Polynomial([0.,1.,1/32])
        def compose(poly):
            result=Polynomial([0.])
            for coefficient in poly:result=result*q+coefficient
            return result.coef[::-1]
        physical=signal.tf2ss(compose(b),compose(a))
        drive=np.random.default_rng(628).normal(size=2000)
        _,expected,_=signal.lsim(physical,np.r_[drive,0.],np.arange(len(drive)+1)*2*np.pi*.5e6/100e6,interp=False)
        actual=analog_filter(drive,100e6,family='rx_finite_zero',cutoff_hz=.5e6,integrator_ratio=32.)
        np.testing.assert_allclose(actual,expected[1:],atol=1e-9)
        _,ideal=analog_modes('rx_finite_zero')
        _,tuned=analog_modes('rx_finite_zero',integrator_ratio=32.,retune_ratio=32.)
        for pole in ideal:self.assertLess(min(abs(tuned-pole)),1e-11)
        for operation in (
            lambda:analog_filter(drive,100e6,family='rx_finite_zero',cutoff_hz=.5e6,integrator_ratio=16.),
            lambda:filter_settling_requirement(family='rx_finite_zero',cutoff_hz=.5e6,integrator_ratio=16.)):
            with self.assertRaises(ValueError):operation()

    def test_voltage_scaled_filter_and_noise_normalization(self):
        import itertools
        from scipy import linalg,integrate
        from selected_rf import rx_filter_state_space,analog_modes
        frequency=np.r_[0.,np.geomspace(.001,10.,80)]
        residues,poles=analog_modes('rx_finite_zero',integrator_ratio=32.,retune_ratio=32.)
        reference=np.sum(residues/(1j*frequency[:,None]-poles),axis=1)
        for order in itertools.permutations(range(3)):
            for pairing in ((0,1),(1,0)):
                m=rx_filter_state_space(order=order,zero_pairing=pairing,integrator_ratio=32.,retune_ratio=32.)
                A,B,C=m['A'],m['B'],m['C']
                actual=np.array([C@np.linalg.solve(1j*f*np.eye(len(B))-A,B)+m['D'] for f in frequency])
                np.testing.assert_allclose(actual,reference,atol=1e-10)
        # Independently integrate the positive-frequency PSD, including the
        # rad/s -> Hz and one-sided factors, rather than another Lyapunov solve.
        for v in (B,*m['noise_inputs'].T):
            P=linalg.solve_continuous_lyapunov(A,-np.outer(v,v))
            analytic=float(C@P@C)/2
            numeric,error=integrate.quad(lambda w:float(abs(C@np.linalg.solve(1j*w*np.eye(len(B))-A,v))**2)/(2*np.pi),
                0,np.inf,epsabs=1e-10,epsrel=1e-9,limit=300)
            self.assertGreater(analytic,0.)
            self.assertLess(error,1e-7)
            self.assertAlmostEqual(analytic,numeric,places=7)

    def test_rc_resistor_noise_and_allocation_dual(self):
        from scipy import linalg
        from selected_rf import rx_filter_state_space
        from selected_revision_check import reciprocal_allocation_lower_bound
        m=rx_filter_state_space(order=(2,1,0))
        index=m['noise_names'].index('pole');alpha=m['normalized_integrator_rates'][index]
        self.assertEqual(m['resistor_conductance_weights'][index],2.)
        cap=40e-12;rate=2*np.pi*9.53125e6;kT=1.380649e-23*300.15
        resistance=1/(rate*alpha*cap)
        density=4*kT*2*resistance
        n=m['noise_inputs'][:,index]
        P=linalg.solve_continuous_lyapunov(m['A'],-np.outer(n,n))
        variance=rate/2*density*(m['C']@P@m['C'])
        # Active equal-R input/feedback integrator pole has two independent
        # resistor sources; it is not the single-resistor passive kT/C case.
        self.assertAlmostEqual(float(variance/(2*kT/cap)),1.,places=10)
        weights=np.array([2.,3.]);M=np.array([[4.,5.]])
        scale=np.sqrt(weights*M[0]).sum()
        optimum=np.sqrt(M[0]/weights)*scale
        bound=reciprocal_allocation_lower_bound(M,weights,optimum)
        self.assertAlmostEqual(bound['lower_bound'],scale**2,places=9)
        self.assertLess(abs(bound['gap']),1e-9)
        loose=reciprocal_allocation_lower_bound(M,weights,optimum*2)
        self.assertLessEqual(loose['lower_bound'],scale**2)
        self.assertLess(loose['lower_bound'],loose['evaluated_objective'])

    def test_wideband_noiseless_resolution_and_payload_observation(self):
        # Independent ideal-rail/filter convergence fixture; no shared-chip claim.
        from selected_rf import wideband_receive
        e=dict(carrier_hz=2.4e9,delivered_phase_tones=[],reference_fraction_tones=[],
            ledger=dict(local_payload_clock_core_rail_v=3.3),host_spectrum=dict(tones=[]))
        results=[wideband_receive(e,oversample=n,wanted_dbm=-65.,blocker_dbm=None,
            noise=False,gain_settings_db=(42.,)) for n in (64,128)]
        observations=[r['gain_cases'][0]['observation'] for r in results]
        self.assertTrue(all(r['bpsk_errors']==0 for r in observations))
        self.assertTrue(all(r['evm_rms']<.05 for r in observations))
        self.assertLess(abs(observations[0]['evm_rms']-observations[1]['evm_rms']),.002)

    def test_linear_forcing_against_independent_state_space(self):
        from scipy import signal
        from selected_rf import analog_filter
        rng=np.random.default_rng(82)
        drive=rng.normal(size=1200)+1j*rng.normal(size=1200)
        for family,ba in (
            ('rx_finite_zero',signal.ellip(5,1,36.40776933523119,1,analog=True)),
            ('rx_all_pole_control',signal.butter(5,1,analog=True)),
            ('tx_third_order',signal.butter(3,1,analog=True))):
            times=np.arange(len(drive))*2*np.pi*9e6/1e9
            state=signal.tf2ss(*ba)
            _,real,_=signal.lsim(state,drive.real,times,interp=True)
            _,imag,_=signal.lsim(state,drive.imag,times,interp=True)
            actual=analog_filter(drive,1e9,family=family,cutoff_hz=9e6,interpolation='linear')
            np.testing.assert_allclose(actual,real+1j*imag,atol=1e-10)
            self.assertLess(abs(actual[0]),1e-14)

    def test_diagnostic_training_does_not_replace_held_out_payload(self):
        from selected_rf import he_source,he_observation
        wave,_=he_source(oversample=4)
        clean=np.asarray(wave.samples)
        same=he_observation(wave,clean,diagnostic_training=clean)
        self.assertEqual(same['bpsk_errors'],0)
        self.assertTrue(same['diagnostic_external_training'])
        damaged=clean.copy()
        n=256+wave.metadata['cp']
        damaged[2*n:]=0
        result=he_observation(wave,damaged,diagnostic_training=clean)
        self.assertGreater(result['bpsk_errors'],0)
        self.assertAlmostEqual(result['evm_rms'],1.)

    def test_nonuniform_dac_edges_against_independent_state_space(self):
        from scipy import signal, linalg
        from selected_rf import analog_hold_at
        values=np.array([.2+.1j,-.3+.05j,.4-.2j,0j])
        edges=np.array([0.,26.7e-9,53.2e-9,80.05e-9])
        queries=np.linspace(-1e-9,120e-9,61)
        a,b,c,d=signal.tf2ss(*signal.butter(3,1,analog=True))
        augmented=np.zeros((4,4));augmented[:3,:3]=a;augmented[:3,3:]=b
        state=np.zeros(3,complex);current=0j;previous=-1e-9;reference=[]
        # Exact real state-space evolution over the union of event/query times.
        for time in sorted(set(edges)|set(queries)):
            evolution=linalg.expm(augmented*(time-previous)*2*np.pi*20e6)
            state=evolution[:3,:3]@state+evolution[:3,3]*current
            if time in edges:current=values[np.flatnonzero(edges==time)[0]]
            if time in queries:reference.append((c@state)[0])
            previous=time
        modeled=analog_hold_at(values,edges,queries,family='tx_third_order',cutoff_hz=20e6)
        np.testing.assert_allclose(modeled,reference,atol=1e-12)


class SelectedPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from baseline_envelope import configured_environment, joined_scan_request,receiver_inventory_options
        from converter_dynamics import SARParameters,load_response
        cls.design=load_design();cls.contract=cls.design.contract
        cls.environment=configured_environment(cls.design.configure(engine='rf',direction='rx',
            reference_hz=2.426e9,sample_divider=256,pga_gain_db=39))
        # Independently settled TX fixture; no continuous RX load-tail handoff.
        cls.tx_environment=configured_environment(cls.design.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=256))
        # Strong diagnostic packet exercises timing/underflow, not sensitivity.
        options=dict(receiver_inventory_options(cls.environment),seed=317,
            wanted_dbm=-67.,blocker_dbm=-50.,rx_cutoff_hz=.5e6,
            blocker_offsets_hz=(2e6,4e6),
            aperture_rms_s=10e-12,dynamic_rail=True,mixer_substeps=512)
        capture={}
        joined_scan_request(cls.environment,cls.contract,**options,load_capture=capture)
        from selected_rf import reference_supply_parameters,clock_supply_delay_pole,clock_supply_sensitivity
        response,_=load_response(capture,cls.environment['network'],
            reference_supply_parameters=reference_supply_parameters(cls.environment),
            delay_pole_hz=clock_supply_delay_pole(cls.environment),
            sensitivity_ps_per_mv=clock_supply_sensitivity(cls.environment))
        cls.environment=dict(cls.environment,local_load_response=response)
        cls.request=joined_scan_request(cls.environment,cls.contract,**options)
        cls.options=dict(reconstruction_order=3,aperture_rms_s=10e-12,
            dynamic_rail=True,rf_bias_a=cls.tx_environment['ledger']['owner_current_a']['rf'],rx_timestamp_correction_s=1.19e-6,tx_launch_advance_s=.32e-6,mixer_substeps=512)

    def test_actual_host_availability_cannot_be_backdated(self):
        from ble_packet import response_budget
        r=self.request
        options=dict(advertiser_address=bytes.fromhex('a6a5a4a3a2c1'))
        base=response_budget(r['observation'],r['settings'],self.environment,self.contract,**options)
        late=base['target_air_start_s']+1e-6
        result=response_budget(r['observation'],r['settings'],self.environment,self.contract,
            host_samples_ready_s=late,**options)
        self.assertFalse(result['reply_armed'])
        self.assertGreater(result['ready_s'],late)
        self.assertEqual(result['target_air_start_s'],base['target_air_start_s'])
        self.assertEqual(result['events'][0]['state'],'wait_for_actual_host_record')
        self.assertNotIn('deliver_last_required_samples',[x['state'] for x in result['events']])
        invalid=response_budget(dict(r['observation'],crc_ok=False),r['settings'],self.environment,self.contract,
            host_samples_ready_s=0.,**options)
        self.assertFalse(invalid['reply_armed'])

    def test_conversion_latency_is_charged_to_availability_not_source_timestamp(self):
        from ble_packet import response_budget
        r=self.request
        instantaneous=response_budget(r['observation'],r['settings'],self.environment,self.contract,
            advertiser_address=bytes.fromhex('a6a5a4a3a2c1'))
        latency=sum(self.environment['converter_parameters']['bit_durations_s'])
        self.assertAlmostEqual(r['response']['ready_s']-instantaneous['ready_s'],latency,places=14)
        self.assertEqual(r['response']['target_air_start_s'],instantaneous['target_air_start_s'])
        self.assertEqual(r['response']['events'][0]['state'],'complete_last_required_conversion')
        self.assertIsNone(r['adc_enob'])
        self.assertGreater(r['converter']['reference_charge_drawn_c'],0.)

    def test_five_pole_reply_inherits_filter_and_decodes_at_peer(self):
        from selected_revision_check import five_pole_tx_candidate
        from baseline_envelope import configured_environment
        from ble_packet import transmitted_scan_response
        design=five_pole_tx_candidate(self.design)
        environment=configured_environment(design.configure(engine='rf',direction='tx',
            reference_hz=2.426e9,sample_divider=256))
        # Reuse the decoded FPGA request and its timestamp; TX is independently
        # settled here, not a claim about a continuous RX-to-TX handoff.
        options=dict(self.options,reconstruction_order=None,
            rf_bias_a=environment['ledger']['owner_current_a']['rf'])
        sent=transmitted_scan_response(self.request,environment,design.contract,**options)
        self.assertEqual(sent['reconstruction_order'],5)
        self.assertIsNone(sent['reconstruction_diagnostic_override'])
        self.assertTrue(sent['exact_nonuniform_reconstruction'])
        self.assertTrue(sent['peer_correct_response'])

    def test_selected_packet_has_no_source_timestamp_oracle_and_honors_underflow(self):
        from ble_packet import transmitted_scan_response
        self.assertTrue(self.request['correct_request'])
        self.assertTrue(self.request['gain_control']['native_transport_low_two_bits_zero'])
        sent=transmitted_scan_response(self.request,self.tx_environment,self.contract,**self.options)
        self.assertEqual(sent['design_provenance'],self.design.provenance())
        self.assertEqual(sent['resolved_configuration']['direction'],'tx')
        self.assertEqual(sent['converter_bits'],
            self.tx_environment['transmitter_parameters']['dac_i']['native_bits'])
        self.assertEqual(sent['resolved_configuration']['sample_hz'],self.request['settings']['sample_hz'])
        self.assertTrue(sent['peer_correct_response'])
        self.assertTrue(sent['exact_nonuniform_reconstruction'])
        self.assertEqual(sent['playback']['peak_occupancy_samples'],32)
        self.assertEqual(sent['playback']['depth_samples'],42)
        self.assertEqual(sent['electrical']['total_rail_bias_a'],
            self.tx_environment['ledger']['owner_current_a']['rf'])
        changed=dict(self.request,source_packet_end_s=self.request['source_packet_end_s']+1e-3)
        other=transmitted_scan_response(changed,self.tx_environment,self.contract,**self.options)
        self.assertEqual(other['first_dac_consumption_s'],sent['first_dac_consumption_s'])
        self.assertEqual(other['peer'],sent['peer'])
        self.assertAlmostEqual(other['scoreboard_rf_half_amplitude_gap_s'],
            sent['scoreboard_rf_half_amplitude_gap_s']-1e-3,places=12)
        stalled=transmitted_scan_response(self.request,self.tx_environment,self.contract,
            **self.options,host_gap_s=10e-6)
        self.assertEqual(stalled['playback']['fault'],'underflow')
        self.assertEqual(stalled['playback']['consumed_samples'],32)
        self.assertFalse(stalled['peer_correct_response'])


class ConverterDynamicsTests(unittest.TestCase):
    def test_discharged_reference_charges_from_current_limit_and_continues(self):
        from converter_dynamics import paired_sar,discharged_sar_state
        t=np.arange(1,13)*30e-9;z=np.full(len(t),.3+.2j)
        forcing=(lambda q:np.ones_like(q),lambda q:np.full_like(q,3.3))
        state=discharged_sar_state()
        whole,report,trace=paired_sar(z,z,t,*forcing,noise=False,initial_state=state,idle_step_s=1e-9)
        # Before the first conversion draws charge, I*t/C determines Vref.
        self.assertAlmostEqual(trace['acquisition_reference_v'][0],.001*t[0]/100e-12,places=12)
        self.assertEqual(report['initial_reference_v'],0.)
        self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-20)
        parts=[]
        for begin,end in ((0,4),(4,len(t))):
            words,_,part=paired_sar(z[begin:end],z[begin:end],t[begin:end],*forcing,
                noise=False,initial_state=state,idle_step_s=1e-9)
            state=part['final_state'];parts.extend(words)
        np.testing.assert_array_equal(parts,whole)
        self.assertEqual(state,trace['final_state'])
        invalid=discharged_sar_state();invalid['reference_v']=-.1
        with self.assertRaises(ValueError):paired_sar(z,z,t,*forcing,initial_state=invalid)

    def test_native_load_continuation_matches_unbroken_activity_and_rejects_reset_errors(self):
        from converter_dynamics import sampled_load_response
        from baseline_envelope import clock_screen_environment
        design=load_design();contract=design.contract
        e,_=clock_screen_environment(design,'rf',2.426e9)
        e['reference_load_parameters']=dict(differential=contract['physical_services']['external_clock_input']['input_model'])
        t=330e-6+np.arange(3200)*.125e-9
        current=np.zeros(len(t));current[100:1500]=-.007;current[1700:2500]=-.004
        whole,_=sampled_load_response(t,current,e,guard_s=20e-9)
        first,_=sampled_load_response(t[:1500],current[:1500],e,guard_s=2e-6)
        state=json.loads(json.dumps(first['final_state']))
        continued,report=sampled_load_response(t[1700:],current[1700:],e,initial_state=state,guard_s=20e-9)
        reset,_=sampled_load_response(t[1700:],current[1700:],e,guard_s=20e-9)
        for field in ('rail_v','input_v','return_v','reference_fraction'):
            np.testing.assert_allclose(continued[field][:1500],whole[field][1700:3200],rtol=0,atol=1e-11)
        np.testing.assert_allclose(continued['delay_s'][:1500],whole['delay_s'][1700:3200],rtol=0,atol=1e-21)
        self.assertGreater(np.max(abs(reset['rail_v'][:1500]-whole['rail_v'][1700:3200])),.0004)
        self.assertAlmostEqual(report['quiet_gap_s'],25e-9,delta=1e-18)
        self.assertEqual(report['initial_state'],'continued')
        with self.assertRaises(ValueError):sampled_load_response(t[1400:1500],current[1400:1500],e,initial_state=state)
        with self.assertRaises(ValueError):sampled_load_response(t[1700:],current[1700:],dict(e,local_supply_delay_sign=-1.),initial_state=state)
        with self.assertRaises(ValueError):sampled_load_response(t[1700:],current[1700:],e,initial_state=state,method='coarse_fft')

    def test_native_current_propagation_keeps_source_grid_and_is_causal(self):
        from converter_dynamics import sampled_load_response
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        environment=dict(network=c,reference_load_parameters=dict(differential=dict(mismatch=.2,opposed=False,cm_gain=-.1)))
        t=330e-6+np.arange(640)*.03125e-9
        current=.001*np.cos(2*np.pi*625e6*(t-t[0]))
        a,report=sampled_load_response(t,current,environment,grid_s=1e-9,guard_s=20e-9)
        changed=current.copy();changed[320:]*=-1
        b,_=sampled_load_response(t,changed,environment,grid_s=.5e-9,guard_s=20e-9)
        self.assertEqual(report['method'],'native_modal_zoh')
        self.assertAlmostEqual(report['grid_s'],.03125e-9,delta=1e-18)
        self.assertEqual(report['requested_grid_s'],1e-9)
        self.assertEqual(a['resolved_offset_hz'],0.)
        self.assertAlmostEqual(a['native_source_step_s'],.03125e-9,delta=1e-18)
        self.assertLess(report['modal_transfer_maximum_error_ohm'],1e-6)
        for field in ('rail_v','input_v','return_v','delay_s','reference_fraction'):
            np.testing.assert_array_equal(a[field][:320],b[field][:320])
        self.assertGreater(np.max(abs(a['rail_v'][320:]-b['rail_v'][320:])),1e-5)

    def test_feedback_agreement_cannot_hide_clock_input_error_in_equal_rails(self):
        from converter_dynamics import feedback_change
        t=np.arange(10)*1e-9
        response=dict(times_s=t,rail_v=np.zeros(10),input_v=np.zeros(10),delay_s=np.zeros(10))
        self.assertTrue(feedback_change(response,response)['converged'])
        changed=dict(response,input_v=np.full(10,2e-6))
        report=feedback_change(changed,response)
        self.assertFalse(report['converged'])
        self.assertTrue(report['fields']['rail_v']['within_limit'])
        self.assertFalse(report['fields']['input_v']['within_limit'])
        self.assertFalse(feedback_change(dict(response,delay_s=np.full(10,2e-15)),response)['converged'])

    def test_sampled_tx_load_conserves_charge_and_superposes_absolute_time(self):
        from converter_dynamics import sampled_load_response,sum_load_responses
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        t=20e-6+np.arange(3000)*.25e-9
        current=np.zeros(len(t));current[100:2500]=-.007
        environment=dict(network=c)
        response,report=sampled_load_response(t,current,environment)
        self.assertAlmostEqual(report['integrated_charge_c'],-.007*2400*.25e-9,places=19)
        self.assertLess(abs(report['resampling_charge_error_c']),1e-20)
        self.assertLess(abs(response['rail_v'][-1]),1e-6)
        doubled=sum_load_responses(response,response)
        np.testing.assert_allclose(doubled['rail_v'],2*np.interp(doubled['times_s'],response['times_s'],response['rail_v'],left=0.,right=0.),atol=1e-14)
        self.assertGreater(response['times_s'][0],17e-6)
        zero,zr=sampled_load_response(t,np.zeros_like(t),environment)
        np.testing.assert_array_equal(zero['rail_v'],np.zeros_like(zero['rail_v']))
        with self.assertRaises(ValueError):sampled_load_response(t[::-1],current,environment)

    def test_fixed_reference_current_accounting_preserves_prefix_and_dc(self):
        from converter_dynamics import paired_sar,load_response
        candidate=shared_board_candidate()
        candidate['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        t=(np.arange(80)+1)*30e-9;z=.3*np.exp(2j*np.pi*1.7e6*t)
        forcing=(lambda q:np.ones_like(q),lambda q:np.full_like(q,3.))
        _,_,short=paired_sar(z[:40],z[:40],t[:40],*forcing,noise=False)
        _,_,long=paired_sar(z,z,t,*forcing,noise=False)
        # Finer grid limits noncausal FFT truncation residue; the baseline itself
        # is independent of trace length. This is not exact time-domain causality.
        a,ar=load_response(short,candidate,dc_reference_a=.001,grid_s=.125e-9)
        b,br=load_response(long,candidate,dc_reference_a=.001,grid_s=.125e-9)
        early=a['times_s']<t[35]
        np.testing.assert_allclose(a['rail_v'][early],np.interp(a['times_s'][early],b['times_s'],b['rail_v']),rtol=0,atol=1e-7)
        quiet=dict(segments=np.array([[0.,100e-9,1.,1.,50.,0.]]),reference_cap_f=100e-12,reference_limit_a=.001)
        q,report=load_response(quiet,candidate,dc_reference_a=.001)
        resistance=candidate['network']['feed_r']+candidate['network']['package_r']+candidate['return_r_ohm']
        np.testing.assert_allclose(q['rail_v'],.001*resistance,rtol=0,atol=1e-12)
        from selected_rf import load_value
        for field,value in q['background'].items():
            np.testing.assert_allclose(load_value(dict(local_load_response=q),np.array([-1.,1.]),field),value,rtol=0,atol=1e-18)
            np.testing.assert_allclose(q[field],value,rtol=0,atol=1e-12)
        self.assertGreater(q['background']['rail_v'],0.)

        self.assertEqual(report['current_accounting'],'fixed_reserved_current_replaced_by_actual_recharge')
        with self.assertRaises(ValueError):load_response(quiet,candidate,dc_reference_a=.002)

    def test_causal_recharge_extension_preserves_committed_prefix(self):
        from converter_dynamics import paired_sar,load_response,parameters_from_inventory
        from baseline_envelope import configured_environment,reference_load_parameters
        design=load_design()
        env=configured_environment(design.configure(engine='rf',direction='rx',reference_hz=2.426e9,sample_divider=128,pga_gain_db=27))
        p=parameters_from_inventory(design.architecture)
        t=(np.arange(80)+1)*60e-9;z=.3*np.exp(2j*np.pi*1.7e6*t)
        forcing=(lambda q:np.full_like(q,design.architecture['blocks']['refbuf']['parameters']['target_v']),lambda q:np.full_like(q,3.3))
        _,_,short=paired_sar(z[:40],z[:40],t[:40],*forcing,noise=False,parameters=p)
        _,_,long=paired_sar(z,z,t,*forcing,noise=False,parameters=p)
        kwargs=dict(dc_reference_a=p.reference_limit_a,grid_s=.125e-9,
            reference_input=reference_load_parameters(dict(env,reference_load_parameters=dict(differential=design.contract['physical_services']['external_clock_input']['input_model']))),
            reference_supply_parameters=env['reference_supply_parameters'])
        a,ar=load_response(short,env['network'],method='native_modal',**kwargs)
        b,br=load_response(long,env['network'],method='native_modal',**kwargs)
        early=a['times_s']<t[39]-p.acquisition_s
        for field in ('rail_v','input_v','return_v','reference_fraction','delay_s'):
            np.testing.assert_allclose(a[field][early],b[field][:len(a[field])][early],rtol=0,atol=1e-12)
        self.assertAlmostEqual(ar['source_charge_c'],sum(np.maximum(0,short['segments'][:,5])),places=20)
        self.assertEqual(ar['method'],'native_modal_zoh')

    def test_sar_cycle_guard_cannot_be_bypassed_by_split_calls(self):
        from converter_dynamics import paired_sar,SARParameters
        p=SARParameters(unmodeled_cycle_uncertainty_s=.2e-9)
        forcing=(lambda t:np.ones_like(t),lambda t:np.full_like(t,3.3))
        z=np.array([.2+.1j,.1+.2j]);first=1e-6
        # 25 ns fits acquisition/conversion/reset, but omits the guard.
        with self.assertRaises(ValueError):
            paired_sar(z,z,[first,first+25e-9],*forcing,parameters=p,noise=False)
        _,_,prefix=paired_sar(z[:1],z[:1],[first],*forcing,parameters=p,noise=False)
        state=prefix['final_state']
        with self.assertRaisesRegex(ValueError,'cycle guard'):
            paired_sar(z[1:],z[1:],[first+25e-9],*forcing,
                parameters=p,noise=False,initial_state=state)
        valid=[first,first+25.3e-9]
        whole,_,_=paired_sar(z,z,valid,*forcing,parameters=p,noise=False)
        tail,_,_=paired_sar(z[1:],z[1:],valid[1:],*forcing,
            parameters=p,noise=False,initial_state=state)
        np.testing.assert_array_equal(tail,whole[1:])

    def test_sar_continuation_preserves_charge_noise_and_idle_gap(self):
        import json
        from converter_dynamics import paired_sar
        t=(np.arange(48)+1)*30e-9;t[19:]+=200e-9
        z=.3*np.exp(2j*np.pi*1.7e6*t)
        forcing=(lambda q:1.+.01*np.sin(2*np.pi*1e6*q),lambda q:3.+.02*np.cos(2*np.pi*2e6*q))
        for noise,idle_step in ((False,None),(True,None),(False,1e-9),(True,1e-9)):
            whole,_,full=paired_sar(z,z,t,*forcing,noise=noise,idle_step_s=idle_step)
            state=None;words=[];segments=[]
            for begin,end in ((0,7),(7,19),(19,48)):
                part,report,trace=paired_sar(z[begin:end],z[begin:end],t[begin:end],*forcing,noise=noise,initial_state=state,idle_step_s=idle_step)
                words.extend(part);segments.extend(trace['segments'])
                self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-17)
                state=json.loads(json.dumps(trace['final_state']))
            np.testing.assert_array_equal(words,whole)
            np.testing.assert_array_equal(segments,full['segments'])
            self.assertEqual(state,json.loads(json.dumps(full['final_state'])))
            with self.assertRaises(ValueError):
                paired_sar(z[:1],z[:1],[state['end_time_s']+1e-9],*forcing,initial_state=state)

        from copy import deepcopy
        from unittest.mock import Mock
        reference=Mock(side_effect=AssertionError('Rejected state consumed reference'))
        rail=Mock(side_effect=AssertionError('Rejected state consumed rail'))
        for change in ({'version':0},{'parameters':'different circuit'},
                       {'comparator_model':'different comparator'},
                       {'end_time_s':float('inf')},{'reference_v':-1.},
                       {'held':[float('nan'),0.]},{'dac':[0.,float('inf')]},
                       {'last_code':[float('inf'),0.]},{'rng_state':{}}):
            invalid=deepcopy(state);invalid.update(change)
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError,KeyError)):
                paired_sar(z[:1],z[:1],[state['end_time_s']+30e-9],
                    reference,rail,initial_state=invalid)
            reference.assert_not_called();rail.assert_not_called()
        missing=deepcopy(state);del missing['comparator_model']
        with self.assertRaisesRegex(ValueError,'Compatible SAR continuation'):
            paired_sar(z[:1],z[:1],[state['end_time_s']+30e-9],reference,rail,initial_state=missing)
        with self.assertRaisesRegex(ValueError,'Continuation must allow'):
            paired_sar(z[:1],z[:1],[state['end_time_s']+1e-9],reference,rail,initial_state=state)
        reference.assert_not_called();rail.assert_not_called()

    def test_live_gain_uses_completed_words_and_is_independent_of_future_input(self):
        from converter_dynamics import paired_sar,ObservedGain,SARParameters
        p=SARParameters();t=(np.arange(400)+1)/10e6
        z=np.full(400,1e-4+1e-4j);z[200:]=.2+.2j
        controllers=[];outputs=[]
        for n in (400,200):
            controller=ObservedGain(sample_hz=10e6,command_latency_s=2e-6,
                acquisition_s=p.acquisition_s,headroom_start=np.full(n,.7),headroom_end=np.full(n,.7))
            words,_,_=paired_sar(z[:n],z[:n],t[:n],lambda t:np.ones_like(t),
                lambda t:np.full_like(t,3.),input_control=controller)
            outputs.append(words);controllers.append(controller)
        np.testing.assert_array_equal(outputs[0][:200],outputs[1])
        self.assertEqual(controllers[0].trace[:200],controllers[1].trace)
        for command in controllers[0].commands:
            self.assertAlmostEqual(command['code_available_s'],t[command['last_observed_code']]+18e-9,places=15)
            self.assertAlmostEqual(command['earliest_apply_s']-command['code_available_s'],2e-6,places=15)
        self.assertGreater(controllers[0].updates,0)

    def test_limited_reference_and_dac_match_independent_ode(self):
        from scipy.integrate import solve_ivp
        from converter_dynamics import recover
        for tau in (.15e-9,1e-9):
            r=10.;c=100e-12;limit=.001;code=.6-.2j
            def ode(t,y):
                current=np.clip((1-y[0])/r,-limit,limit)
                return np.array([current/c,(code.real*y[0]-y[1])/tau,
                    (code.imag*y[0]-y[2])/tau])*1e-9
            answer=solve_ivp(ode,(0,15),[.9,.2,-.1],rtol=1e-10,atol=1e-12).y[:,-1]
            ref,dac,charge=recover(.9,.2-.1j,1.,code,15e-9,r=r,c=c,limit=limit,tau=tau)
            np.testing.assert_allclose([ref,dac.real,dac.imag],answer,atol=2e-10)
            self.assertAlmostEqual(charge,c*(ref-.9),places=20)

    def test_ideal_limit_native_codes_and_conserved_reference_charge(self):
        from converter_dynamics import paired_sar,SARParameters,load_response
        from dataclasses import replace
        z=np.arange(-512,512)/512+1j*np.arange(511,-513,-1)/512
        t=(np.arange(len(z))+1)*30e-9
        p=replace(SARParameters(),sample_resistance_ohm=.01,dac_tau_s=1e-13,dac_effective_cap_f=1e-21)
        words,report,_=paired_sar(z,z,t,lambda t:np.ones_like(t),lambda t:np.full_like(t,3.3),parameters=p,noise=False)
        np.testing.assert_array_equal(words[:,0],np.arange(-512,512)*4)
        np.testing.assert_array_equal(words[:,1],np.arange(511,-513,-1)*4)
        # With finite capacitance, compare a prefix to a longer trajectory;
        # neither code decisions nor reference recovery may depend on future input.
        x=.3*np.exp(2j*np.pi*3e6*t)
        args=(lambda t:np.ones_like(t),lambda t:np.full_like(t,3.0))
        whole,report,trace=paired_sar(x,x,t,*args,noise=True)
        prefix,_,_=paired_sar(x[:100],x[:100],t[:100],*args,noise=True)
        np.testing.assert_array_equal(whole[:100],prefix)
        self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-17)
        self.assertGreater(report['reference_source_average_a'],0)
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        _,load=load_response(trace,c)
        self.assertLess(abs(load['charge_resampling_residual_c']),1e-17)
        positive,_=load_response(trace,c,reference_input={},supply_sign=1.)
        negative,_=load_response(trace,c,reference_input={},supply_sign=-1.)
        for field in ('rail_v','input_v','reference_fraction'):
            np.testing.assert_array_equal(positive[field],negative[field])
        np.testing.assert_allclose(positive['delay_s'],-negative['delay_s'],atol=1e-25)
        reduced,_=load_response(trace,c,reference_input={},sensitivity_ps_per_mv=.025)
        immune,_=load_response(trace,c,reference_input={},sensitivity_ps_per_mv=0.)
        for field in ('rail_v','input_v','reference_fraction'):
            np.testing.assert_array_equal(positive[field],reduced[field])
            np.testing.assert_array_equal(positive[field],immune[field])
        np.testing.assert_allclose(reduced['delay_s'],positive['delay_s']/4,atol=1e-25)
        np.testing.assert_array_equal(immune['delay_s'],np.zeros_like(immune['delay_s']))
        for invalid in (-.1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):load_response(trace,c,sensitivity_ps_per_mv=invalid)
        # The time-domain feedback must preserve common-mode rejection, not
        # feed a single leg into the differential threshold solver.
        paired,load=load_response(trace,c,reference_input=dict(differential=dict(mismatch=.2,opposed=False,cm_gain=-.1)))
        legs=paired['input_leg_v']
        np.testing.assert_allclose(paired['input_v'],legs[:,0]-legs[:,1]-.1*np.mean(legs,axis=1),atol=1e-18,rtol=1e-10)
        np.testing.assert_allclose(load['input_leg_voltage_abs_peak_v'],np.max(abs(legs),axis=0))
        balanced,_=load_response(trace,c,reference_input=dict(differential=dict(mismatch=0.,opposed=False,cm_gain=0.)))
        np.testing.assert_array_equal(balanced['input_v'],np.zeros_like(balanced['input_v']))
        self.assertGreater(float(np.max(abs(balanced['input_leg_v']))),0.)
        from baseline_envelope import reference_feedback_response
        from selected_rf import driver_wake_response
        env=dict(network=c,periodic_clock={},reference_load_parameters=dict(differential=dict(mismatch=.2,opposed=False,cm_gain=-.1)),
            local_supply_delay_sign=-1.,local_supply_sensitivity_ps_per_mv=.025)
        actual,report=reference_feedback_response(trace,env)
        expected,_=load_response(trace,c,reference_input=env['reference_load_parameters'],supply_sign=-1.,sensitivity_ps_per_mv=.025,dc_reference_a=trace['reference_limit_a'])
        self.assertEqual(report['current_accounting'],'fixed_reserved_current_replaced_by_actual_recharge')
        for key in ('input_v','input_leg_v','delay_s','rail_v'):
            np.testing.assert_array_equal(actual[key],expected[key])
        automatic,_=driver_wake_response(env,released_current_a=.028,wake_start_s=2e-6)
        explicit,_=driver_wake_response(env,released_current_a=.028,wake_start_s=2e-6,reference_input=env['reference_load_parameters'])
        for key in ('input_v','input_leg_v','delay_s','rail_v'):
            np.testing.assert_array_equal(automatic[key],explicit[key])
        with self.assertRaises(ValueError):load_response(trace,c,supply_sign=0.)

    def test_local_supply_transfer_matches_independent_three_node_network(self):
        from converter_dynamics import local_impedance
        from robustness_envelope import shared_return_transfer
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        for f in (1e3,1e6,37.5e6,625e6,2e9):
            expected=shared_return_transfer(f,injection_weights=(0.,-1.,1.),
                return_r=c['return_r_ohm'],return_l=c['return_l_h'],**c['network'])['differential_ohm']
            self.assertAlmostEqual(abs(local_impedance(f,c)-expected),0.,places=10)


class WiredIntegrationTests(unittest.TestCase):
    def test_internal_usb_return_matches_independent_three_node_mna(self):
        from baseline_envelope import usb_supply_environment,pad_ground_tones,internal_switching_sources
        e,context=usb_supply_environment(load_design())
        self.assertEqual(context['resolved_configuration']['inventory_mode'],'usb')
        before=pad_ground_tones(e)
        e['internal_switching_loads']=[dict(owner='core',mean_a=.02,event_hz=156.25e6,tau_s=.2e-9,harmonics=8)]
        after=pad_ground_tones(e);n=e['network'];net=n['network']
        for f,ports in internal_switching_sources(e['internal_switching_loads']).items():
            omega=2j*np.pi*f;m=np.zeros((3,3),complex)
            def branch(a,b,y):
                m[a,a]+=y
                if b is not None:m[b,b]+=y;m[a,b]-=y;m[b,a]-=y
            def capacitor(c,r,l):return 1/(r+omega*l+1/(omega*c))
            branch(0,None,1/(net['feed_r']+omega*net['feed_l']))
            branch(0,None,capacitor(net['board_c'],net['board_esr'],net['board_esl']))
            branch(0,1,1/(net['package_r']+omega*net['package_l']))
            branch(1,2,capacitor(net['die_c'],net['die_esr'],net['die_esl']))
            branch(2,None,1/(n['return_r_ohm']+omega*n['return_l_h']))
            current=ports[3];expected=np.linalg.solve(m,[0,-current,current])[2]
            np.testing.assert_allclose(after[f]-before.get(f,0j),expected,atol=1e-14,rtol=1e-9)

    def test_usb_dc_voltage_matches_independent_pad_and_board_return_reference(self):
        from baseline_envelope import usb_static_output,usb_supply_environment
        from protocol_pad import SharedWiredPad
        design=load_design()
        e,context=usb_supply_environment(design)
        drive_r=design.architecture['blocks']['usbfs']['parameters']['effective_output_r_ohm']
        self.assertEqual(context['resolved_configuration']['inventory_mode'],'usb')
        ledger=dict(e['ledger'],local_payload_clock_core_rail_v=2.9,die_return_v=0.)
        high=usb_static_output(e,ledger,levels=(1,0),load_ohm=15000.)
        pad=SharedWiredPad();pad.configure('usb',role='device',speed='fs',attached=True)
        pad.set_local_passives();pad.set_local_drive('voltage',levels=(1,0),resistance_ohm=drive_r)
        pad.advance(1e-6,rail=2.9)
        np.testing.assert_allclose(high['dc_output_v'],pad.voltage,atol=1e-6)
        ledger['die_return_v']=.1
        high=usb_static_output(e,ledger,levels=(1,0),load_ohm=15000.)
        self.assertAlmostEqual(high['dc_output_v'][0],3.*15000/(15000+drive_r),places=12)
        low=usb_static_output(e,ledger,levels=(0,0),load_ohm=1500.,load_supply_v=3.6)
        self.assertAlmostEqual(low['dc_output_v'][0],(.1/drive_r+3.6/1500)/(1/drive_r+1/1500),places=12)

        changed=design.hypothetical(reason='USB FS output resistance propagation check',changes={
            'blocks.usbfs.parameters.effective_output_r_ohm':60.})
        other,_=usb_supply_environment(changed)
        output=usb_static_output(other,ledger,levels=(1,0),load_ohm=15000.)
        self.assertEqual(output['driver_ohm'],60.)
        self.assertEqual(output['design_provenance'],changed.provenance())
        self.assertEqual(output['resolved_configuration'],other['resolved_configuration'])
        self.assertEqual(output['scenario_overrides'],other['scenario_overrides'])
        self.assertEqual(output['dc_ledger'],ledger)
        self.assertEqual(output['model_role'],'shared_design_affine_static_pad')
        self.assertEqual(output['diagnostic_assumptions']['external_load_ohm'],15000.)
        output['design_provenance']['documents'].clear()
        output['resolved_configuration'].clear()
        output['scenario_overrides'].append({'unexpected':'mutation'})
        output['dc_ledger']['owner_current_a'].clear()
        self.assertEqual(other['design_provenance'],changed.provenance())
        self.assertTrue(other['resolved_configuration'])
        self.assertEqual(other['scenario_overrides'],[])
        self.assertTrue(ledger['owner_current_a'])
        self.assertAlmostEqual(output['dc_output_v'][0],3.*15000/15060,places=12)
        self.assertNotEqual(output['dc_output_v'][0],high['dc_output_v'][0])
        for invalid in ({}, {'effective_output_r_ohm':0.}, {'effective_output_r_ohm':float('nan')}):
            with self.assertRaisesRegex(ValueError,'resistance'):
                usb_static_output(dict(e,wired_usbfs_parameters=invalid),ledger,levels=(1,0),load_ohm=15000.)
        missing=dict(e);del missing['wired_usbfs_parameters']
        with self.assertRaisesRegex(ValueError,'requires shared'):
            usb_static_output(missing,ledger,levels=(1,0),load_ohm=15000.)

    def test_publication_clock_uses_explicit_owner_across_restart(self):
        from behavioral import TimedBulkRecordReturn
        from bit_event_stream import BitEventStream
        rate=39.0625e6*(1-100e-6);phase=.37;duration=.71e-6
        host=TimedBulkRecordReturn(BitEventStream(128),source_hz=rate,
            source_phase=phase,trained=True)
        host.advance(duration)
        count=int(np.floor(duration*rate-phase))+1
        self.assertEqual(host.source_index,count)
        self.assertAlmostEqual(host.next_source,(count+phase)/rate,places=18)
        host.halt(duration);host.restart(2e-6);host.advance(2e-6+duration)
        self.assertEqual(host.source_index,count)
        self.assertAlmostEqual(host.next_source,2e-6+(count+phase)/rate,places=18)
        with self.assertRaises(ValueError):TimedBulkRecordReturn(BitEventStream(128),source_hz=0.)

    def test_modal_channel_matches_independent_state_space_and_is_causal(self):
        from scipy import signal
        from wired_envelope import physical_receiver
        rate=2.5e9;bits=np.random.default_rng(165).integers(0,2,96).tolist()
        q=dict(jitter_rms_s=0.,jitter_hz=1e6,noise_rms_v=0.,offset_v=0.,
            ctle_zero_s=150e-12,ctle_pole_s=80e-12)
        rx=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,q)
        denominator=np.array([1.])
        for tau in (100e-12,135e-12,80e-12):denominator=np.polymul(denominator,[tau*rate,1.])
        t=np.arange(96*32)/32
        drive=np.repeat(2*np.array(bits)-1,32)
        _,expected,_=signal.lsim(([150e-12*rate,1.],denominator),U=drive,T=t,interp=False)
        observed=np.array([rx.voltage(float(at)) for at in t])
        np.testing.assert_allclose(observed,.4*expected,atol=2e-12,rtol=2e-12)
        prefix=physical_receiver(bits[:48],rate,0.,0.,100e-12,2.7e-12,q)
        np.testing.assert_array_equal(observed[:48*32],np.array([prefix.voltage(float(at)) for at in t[:48*32]]))
        held=physical_receiver(bits,rate,0.,0.,100e-12,2.7e-12,q,hold_final_level=True)
        extended=physical_receiver(bits+[bits[-1]]*16,rate,0.,0.,100e-12,2.7e-12,q)
        tail=np.arange(96,110,.125)
        np.testing.assert_allclose([held.voltage(float(at)) for at in tail],
            [extended.voltage(float(at)) for at in tail],atol=2e-12,rtol=2e-12)


class DriverWakeTests(unittest.TestCase):
    def test_coupled_wake_against_independent_unloaded_state_space(self):
        from selected_rf import driver_wake_response
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        arguments=dict(released_current_a=.028,wake_start_s=2e-6,grid_s=.25e-9)
        exact,_=driver_wake_response(dict(network=c),**arguments)
        spectral,r=driver_wake_response(dict(network=c),**arguments,reference_input=dict(cap_f=0.,link_r_ohm=1e-12))
        difference=abs(exact['rail_v']-spectral['rail_v']);t=exact['times_s']
        # The ideal linear-ramp slope jumps at its corners. Inductive voltage
        # jumps there; a finite Fourier series approaches the midpoint.
        away=(abs(t-2e-6)>2e-9)&(abs(t-2.02e-6)>2e-9)
        self.assertLess(max(difference[away]),20e-6)
        self.assertLess(np.sqrt(np.mean(difference**2)),2e-6)
        self.assertAlmostEqual(r['initial_rail_relief_v'],.028*2.12,places=11)
        short,rs=driver_wake_response(dict(network=c),**arguments,reference_input={})
        long,rl=driver_wake_response(dict(network=c),**arguments,reference_input={},guard_s=16e-6)
        self.assertLess(max(abs(short['rail_v']-long['rail_v'])),1e-6)
        np.testing.assert_allclose(short['driver_current_a'],exact['driver_current_a'],atol=1e-12)

    def test_wake_current_is_within_budget_and_initial_dc_matches_resistors(self):
        from selected_rf import driver_wake_response
        c=shared_board_candidate();c['network'].update(die_c=500e-12,die_esr=.5,die_esl=200e-12)
        for released in (0.,.007,.028):
            response,r=driver_wake_response(dict(network=c),released_current_a=released,
                wake_start_s=2.0003e-6,ramp_s=20.4e-9)
            self.assertAlmostEqual(r['initial_rail_relief_v'],released*2.12,places=12)
            self.assertAlmostEqual(r['driver_current_interval_a'][0],.028-released,places=12)
            self.assertAlmostEqual(r['driver_current_interval_a'][1],.028,places=12)
            self.assertLess(abs(r['final_current_delta_a']),1e-12)
            self.assertLess(abs(r['final_rail_delta_v']),1e-9)
            # Independent charge integral for a linear ramp, including fractional bins.
            t=response['times_s'];current=response['driver_current_a']
            before=t<2.0003e-6;after=t>2.0207e-6
            np.testing.assert_allclose(current[before],.028-released,atol=1e-12)
            np.testing.assert_allclose(current[after],.028,atol=1e-12)
            self.assertAlmostEqual(response['delay_s'][0],released*2.12e-10,places=18)
        with self.assertRaises(ValueError):
            driver_wake_response(dict(network=c),released_current_a=.029,wake_start_s=0.)


class DomainRLCNetworkTests(unittest.TestCase):
    def test_abrupt_host_current_has_nondecaying_inductive_voltage_tail(self):
        from selected_revision_check import domain_rlc_impedance
        from robustness_envelope import h2d_current_ports
        caps=np.array([180,30,30,10,10,180,60])*2e-12
        fraction=caps/sum(caps)
        common_l=1/(1/2e-9+1/1e-9)+.25e-9
        feed_l=np.diag(np.full(7,2e-9))+common_l*np.ones((7,7))
        effective_l=np.linalg.inv(np.linalg.inv(feed_l)+np.diag(fraction/.2e-9))
        distribution=np.array([0,.5,.5,0,0,0,0])
        expected=-effective_l@distribution*(2*11*7e-12*312.5e6/.5e-9)
        harmonic=200000;frequency=harmonic*156.25e6
        current=h2d_current_ports(frequency,312.5e6,harmonic,internal_charge_c=7e-12,alternating=True)['chip_internal_peak_a']
        actual=-domain_rlc_impedance(frequency,caps,1.)@distribution*current
        np.testing.assert_allclose(actual,expected,rtol=2e-4,atol=1e-7)
        self.assertGreater(max(abs(expected)),.001)
        # This is a mathematical asymptote of an unphysical abrupt-edge source,
        # not device/package characterization at the extrapolated frequency.

    def test_reduced_impedance_matches_explicit_board_domain_return_nodes(self):
        from selected_revision_check import domain_rlc_impedance
        caps=np.array([180,30,30,10,10,180,60])*1e-12
        for frequency,esr,explicit in [(f,e,l) for f in (0.,37.5e6,156.25e6,1e9,5e9) for e in (.25,.5,1.,2.) for l in (False,True)]:
            loops=[.2e-9]*7 if explicit else None
            w=2*np.pi*frequency;matrix=np.zeros((9,9),complex)
            def branch(a,b,y):
                matrix[a,a]+=y
                if b is not None:
                    matrix[b,b]+=y;matrix[a,b]-=y;matrix[b,a]-=y
            branch(0,None,1/(.1+1j*w*2e-9))
            branch(8,None,1/(.02+1j*w*.25e-9))
            if w:branch(0,None,1/(.02+1j*w*1e-9+1/(1j*w*1e-6)))
            for j,c in enumerate(caps):
                branch(0,j+1,1/(1+1j*w*2e-9))
                if w:
                    fraction=c/sum(caps)
                    branch(j+1,8,1/(esr/fraction+1j*w*(.2e-9 if explicit else .2e-9/fraction)+1/(1j*w*c)))
            forcing=np.zeros((9,7));forcing[1:8]=np.eye(7);forcing[8]=-1
            solution=np.linalg.solve(matrix,forcing)
            expected=solution[1:8]-solution[8]
            actual=domain_rlc_impedance(frequency,caps,1.,die_esr_ohm=esr,local_cap_esl_h=loops)
            np.testing.assert_allclose(actual,expected,rtol=2e-12,atol=1e-12)
            self.assertGreater(np.linalg.eigvalsh((actual+actual.conj().T)/2).min(),0)
            external=np.zeros(9);external[8]=1
            ground_solution=np.linalg.solve(matrix,external)
            _,ground_transfer=domain_rlc_impedance(frequency,caps,1.,die_esr_ohm=esr,include_external_return=True,local_cap_esl_h=loops)
            np.testing.assert_allclose(ground_transfer,ground_solution[1:8]-ground_solution[8],rtol=2e-12,atol=1e-12)



class LiveAnalogQualificationTests(unittest.TestCase):
    """Independent observation/monitor state-machine and conservation fixtures.

    Startup guards, sample times, pad examples and bare SAR traces are prescribed
    to isolate expiry and fault ordering. Shared contract thresholds are used
    where stated; none of these examples qualifies whole-chip analog readiness.
    """
    def test_independent_monitor_preserves_schedule_and_faults_without_payload_observations(self):
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        def run(split,missing=False,exception=False):
            chip=BehavioralChip(Assumptions(startup_s=0.))
            chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
            chip.configure_transport('exclusive')
            chip.attach_analog_qualification([(0.,True)],max_age_s=200e-9)
            chip.start();chip.advance(0.)
            observations=[]
            def observer(time):
                observations.append(time)
                if exception:raise AnalogQualificationError('Reference outside model domain')
                return None if missing else bool(time<550e-9)
            args=dict(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,
                directions=('tx',),depth_bits=1024,tx_prefill_bits=512,
                tx_source=lambda index:17,analog_observer=observer,
                analog_observation_period_s=100e-9)
            if split:
                self.assertIsNone(chip.transfer(frames=1,**args)['fault'])
            result=chip.transfer(frames=4,**args)
            self.assertEqual(result['fault'],'analog_unqualified')
            self.assertEqual(chip.state,'fault')
            return chip.time,observations,chip.stream['tx_samples']
        whole=run(False);split=run(True)
        self.assertEqual(whole,split)
        self.assertAlmostEqual(whole[0],600e-9,places=15)
        failed=run(False,exception=True)
        self.assertAlmostEqual(failed[0],100e-9,places=15)
        missing=run(False,True)
        self.assertAlmostEqual(missing[0],200e-9,places=15)

    def test_tx_observation_failure_faults_before_word_acceptance(self):
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
        def reject(time,word):
            raise AnalogQualificationError('Measured reference invalid')
        result=chip.transfer(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,
            frames=16,directions=('tx',),depth_bits=1024,tx_prefill_bits=512,
            tx_source=lambda index:17,tx_word_observer=reject)
        self.assertEqual(result['fault'],'analog_unqualified')
        self.assertEqual(chip.state,'fault')
        self.assertEqual(chip.stream['tx_samples'],[])
        with self.assertRaises(ValueError):
            chip.transfer(mode=1,source_hz=250e6,sample_bits=10,epoch=chip.epoch,
                frames=1,directions=('tx',),depth_bits=1024)

    def test_converter_readiness_uses_both_contract_supply_limits(self):
        import copy
        from selected_lifecycle import converter_qualification_events,converter_supply_acceptance
        from converter_dynamics import paired_sar
        from robustness_envelope import P
        contract=load_design().contract
        _,_,trace=paired_sar(np.array([.2+.1j]),np.array([.2+.1j]),np.array([1e-6]),
            lambda t:np.ones_like(t),lambda t:np.full_like(t,3.),noise=False)
        for voltage in (2.4,3.7):
            bad=copy.deepcopy(trace);bad['supply_observations'][-1,1]=voltage
            events,_=converter_qualification_events(contract,bad)
            self.assertFalse(events[-1][1])
            acceptance=converter_supply_acceptance(contract,bad['supply_observations'])
            self.assertEqual(acceptance['invalid_points'],1)
            self.assertEqual(acceptance['first_invalid_time_s'],bad['supply_observations'][-1,0])
        stricter=copy.deepcopy(contract)
        stricter['physical_services']['sar_timing']['startup']['model_supply_window_v']=[2.5,2.9]
        events,_=converter_qualification_events(stricter,trace)
        self.assertFalse(any(valid for _,valid in events))
        self.assertEqual(converter_supply_acceptance(stricter,trace['supply_observations'])['invalid_points'],
                         len(trace['supply_observations']))

    def test_converter_observations_expire_independently_and_gate_chip(self):
        from selected_lifecycle import converter_qualification_events
        from converter_dynamics import paired_sar
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        from resource_configuration import encode_resource_word
        from robustness_envelope import P
        contract=load_design().contract
        _,_,trace=paired_sar(np.array([.2+.1j]),np.array([.2+.1j]),np.array([1e-6]),
            lambda t:np.ones_like(t),lambda t:np.full_like(t,3.),noise=False)
        # Supply remains sampled after converter reference observations stop.
        later=np.arange(1.04e-6,1.5e-6,20e-9)
        trace['supply_observations']=np.r_[trace['supply_observations'],np.c_[later,np.full(len(later),3.)]]
        events,report=converter_qualification_events(contract,trace,max_observation_age_s=100e-9)
        ready=next(time for time,valid in events if valid)
        expiry=next(time for time,valid in events if time>ready and not valid)
        self.assertAlmostEqual(expiry,report['final_reference_observation_s']+100e-9,places=14)
        self.assertLess(expiry,report['final_supply_observation_s'])
        chip=BehavioralChip(Assumptions(startup_s=0.))
        chip.configure(encode_resource_word(engine='rf'));chip.attach_analog_qualification(events)
        chip.start();chip.advance(ready)
        self.assertEqual(chip.state,'active')
        with self.assertRaises(AnalogQualificationError):chip.advance(1.6e-6)
        self.assertAlmostEqual(chip.time,expiry,places=14)

    def test_stale_observations_block_startup_and_reset_continuous_guard(self):
        from behavioral import AnalogQualification
        monitor=AnalogQualification([(0.,True)],max_age_s=.6e-6)
        self.assertEqual(monitor.deadline(0.,1e-6,1e-6),float('inf'))
        monitor.observe(1e-6,True)
        self.assertAlmostEqual(monitor.deadline(0.,1e-6,1e-6),2e-6)
        # A later valid observation must not hide an earlier unsampled interval.
        self.assertAlmostEqual(monitor.loss_between(0.,1e-6),.6e-6)
        monitor.observe(1.5e-6,True);monitor.observe(2e-6,True)
        self.assertIsNone(monitor.loss_between(1e-6,2e-6))
        self.assertAlmostEqual(monitor.deadline(0.,2e-6,1e-6),2e-6)

    def test_stale_analog_monitor_stops_direct_output(self):
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        from resource_configuration import encode_resource_word
        from protocol_pad import SharedWiredPad
        chip=BehavioralChip(Assumptions(startup_s=1e-6))
        chip.configure(encode_resource_word(engine='wire'));chip.configure_transport('direct')
        chip.attach_analog_qualification([(0.,True)],max_age_s=.6e-6)
        pad=SharedWiredPad();pad.configure('usb',speed='hs')
        chip.attach_wired_pad(pad);chip.start()
        for time in (.5e-6,1e-6):
            chip.analog_qualification.observe(time,True);chip.advance(time)
        self.assertEqual(chip.state,'active')
        chip.advance_wired_pad(chip.time);pad.drive(local='J')
        with self.assertRaises(AnalogQualificationError):chip.direct_session.advance(1.7e-6)
        self.assertAlmostEqual(chip.time,1.6e-6)
        self.assertEqual(chip.state,'fault');self.assertEqual(pad.local,'Z')
        chip.stop();chip.start();chip.advance(1.7e-6)
        self.assertEqual(chip.state,'acquiring')

    def test_reference_consumption_points_distinguish_switching_from_invalid_decision(self):
        import copy
        from selected_lifecycle import converter_qualification_events
        from converter_dynamics import paired_sar
        from robustness_envelope import P
        contract=load_design().contract
        _,report,trace=paired_sar(np.array([.2+.1j]),np.array([.2+.1j]),np.array([1e-6]),
            lambda t:np.ones_like(t),lambda t:np.full_like(t,3.),noise=False)
        events,_=converter_qualification_events(contract,trace)
        self.assertLess(report['reference_interval_v'][0],.98)
        self.assertGreaterEqual(report['decision_reference_interval_v'][0],.98)
        self.assertTrue(events[-1][1])
        bad=copy.deepcopy(trace);bad['decision_reference_observations'][-1,1]=.97
        events,_=converter_qualification_events(contract,bad)
        self.assertFalse(events[-1][1])
        bad=copy.deepcopy(trace);bad['supply_observations'][-1,1]=2.4
        events,_=converter_qualification_events(contract,bad)
        self.assertFalse(events[-1][1])

    def test_observation_delays_ready_and_rejects_invalid_source_word(self):
        from behavioral import BehavioralChip,Assumptions,AnalogQualificationError
        chip=BehavioralChip(Assumptions())
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
        chip.attach_analog_qualification([(0.,False)])
        chip.start();chip.advance(20e-6)
        self.assertEqual(chip.state,'acquiring')
        chip.analog_qualification.observe(chip.time,True)
        chip.advance(39e-6);self.assertEqual(chip.state,'acquiring')
        chip.advance(40e-6);self.assertEqual(chip.state,'active')
        origin=chip.time
        def invalid_word(index):
            chip.analog_qualification.observe(origin+(index+1)/250e6,False)
            raise AnalogQualificationError('Observed invalid conversion')
        flow=chip.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=1,
            depth_bits=1024,directions=('rx',),epoch=chip.epoch,rx_source=invalid_word)
        self.assertEqual(flow['fault'],'analog_unqualified')
        self.assertEqual(flow['produced_bits'],0)
        self.assertEqual(chip.state,'fault')
        with self.assertRaises(ValueError):chip.analog_qualification.observe(origin,True)


if __name__=='__main__':unittest.main()

class ConverterDiagnosticLifecycleTests(unittest.TestCase):
    def test_diagnostic_reference_load_is_charged_and_recovered(self):
        from dataclasses import replace
        from converter_dynamics import paired_sar,SARParameters
        times=(np.arange(64)+1)*26.4e-9
        ref=lambda t:np.full_like(t,1.,dtype=float)
        rail=lambda t:np.full_like(t,3.,dtype=float)
        results=[]
        for cap in (0.,.25e-12,1e-12):
            parameters=replace(SARParameters(),diagnostic_reference_effective_cap_per_lane_f=cap)
            words,report,trace=paired_sar(np.zeros(64,complex),np.zeros(64,complex),
                times,ref,rail,parameters=parameters,input_test=(2,3),noise=False)
            self.assertAlmostEqual(report['diagnostic_reference_charge_c'],
                2*cap*sum(trace['acquisition_reference_v']),delta=1e-22)
            self.assertLess(abs(report['reference_charge_balance_residual_c']),1e-20)
            results.append(report)
        self.assertGreater(results[-1]['reference_source_average_a'],results[0]['reference_source_average_a'])
        for codes in ((0,0),(1,1)):
            _,report,_=paired_sar(np.zeros(64,complex),np.zeros(64,complex),times,ref,rail,
                parameters=parameters,input_test=codes,noise=False)
            self.assertEqual(report['diagnostic_reference_charge_c'],0.)

    def test_diagnostic_selection_after_stream_binding_cannot_arm_normal_source(self):
        from behavioral import BehavioralChip
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        design=load_design()
        config=design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=64,pga_gain_db=39)
        chip=BehavioralChip(selected_transport_assumptions(configured_environment(config)))
        chip.configure_numeric(engine='rf',rf=dict(sample_hz=config.sample_hz,
            sample_clock_source='external_lo',lo_hz=config.reference_hz,lo_divider=config.sample_divider,
            rx_cutoff_hz=9.53125e6,tx_cutoff_hz=18e6))
        chip.attach_rf_stream(lambda i:0j)
        core=chip.rf_stream
        for resumed in (False,True):
            if resumed:chip.resume_rf_stream(lambda i:0j)
            chip.configure_converter_input_test(2,3)
            epoch=chip.epoch;index=core.index;time=chip.time
            with self.assertRaisesRegex(ValueError,'normal RF source is attached'):
                chip.start()
            self.assertEqual(chip.state,'reset')
            self.assertEqual((chip.epoch,core.index,chip.time),(epoch,index,time))
            self.assertIs(chip.rf_stream,core)
            chip.configure_converter_input_test(0,0)
            chip.start();chip.advance(chip.ready_at)
            self.assertEqual(chip.state,'active')
            chip.stop()

    def test_ratiometric_codes_do_not_establish_absolute_reference(self):
        from converter_dynamics import paired_sar
        time=(np.arange(32)+1)*26.4e-9
        normal=[];diagnostic=[]
        for voltage in (.8,1.2):
            ref=lambda t:np.full_like(t,voltage,dtype=float)
            rail=lambda t:np.full_like(t,3.,dtype=float)
            for codes,results in (((0,0),normal),((2,3),diagnostic)):
                words,report,trace=paired_sar(np.full(32,.1+.2j),np.full(32,.1+.2j),
                    time,ref,rail,noise=False,input_test=codes)
                results.append(words)
        np.testing.assert_allclose(diagnostic[0],diagnostic[1],atol=4,rtol=0.)
        self.assertGreater(np.max(abs(normal[0]-normal[1])),100)

    def test_stopped_selection_uses_retained_sar_and_rejects_stale_epoch(self):
        from behavioral import BehavioralChip
        from converter_dynamics import parameters_from_inventory
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        design=load_design().hypothetical(reason='Diagnostic reference loading experiment',changes={
            'model_assumptions.paired_sar.parameters.diagnostic_reference_effective_cap_per_lane_f':.25e-12})
        config=design.configure(engine='rf',direction='rx',reference_hz=2.426e9,
            sample_divider=64,pga_gain_db=39.)
        environment=configured_environment(config)
        chip=BehavioralChip(selected_transport_assumptions(environment))
        chip.configure_numeric(engine='rf',rf=dict(sample_hz=config.sample_hz,
            sample_clock_source='external_lo',lo_hz=config.reference_hz,lo_divider=config.sample_divider,
            rx_cutoff_hz=1e6,tx_cutoff_hz=3e6))
        parameters=parameters_from_inventory(design.architecture)
        model=design.architecture['model_assumptions']['paired_sar_comparator']['parameters']
        # Constant rail/reference, noiseless input and no physical startup are
        # intentional fixture simplifications; converter state is retained.
        state=None;reports=[];stale=None
        ref=lambda t:np.full_like(t,1.,dtype=float)
        rail=lambda t:np.full_like(t,3.,dtype=float)
        for codes in ((1,1),(2,3),(0,0)):
            chip.configure_converter_input_test(*codes)
            if any(codes):
                with self.assertRaises(ValueError):chip.attach_rf_stream(lambda i:0j)
            chip.start();chip.advance(chip.ready_at)
            with self.assertRaises(ValueError):chip.configure_converter_input_test(0,0)
            if stale is not None:
                with self.assertRaises(ValueError):stale([],[],[],ref,rail)
            convert=chip.bind_sar_converter(parameters=parameters,noise=False,comparator_model=model)
            times=chip.time+(np.arange(16)+1)/config.sample_hz
            words,report,trace=convert(np.full(16,.1+.2j),np.full(16,.1+.2j),times,
                                       ref,rail,initial_state=state)
            self.assertEqual(report['input_test'],list(codes))
            if state is not None:self.assertEqual(report['initial_reference_v'],state['reference_v'])
            if codes==(1,1):self.assertLess(np.max(abs(words)),12)
            elif codes==(2,3):
                self.assertGreater(np.mean(words[:,0]),450)
                self.assertLess(np.mean(words[:,1]),-450)
            else:
                self.assertGreater(np.mean(words[:,0]),150)
                self.assertGreater(np.mean(words[:,1]),350)
            state=trace['final_state'];reports.append(report)
            chip.advance(state['end_time_s']);chip.stop();stale=convert
        self.assertTrue(all(abs(x['reference_charge_balance_residual_c'])<1e-20 for x in reports))


class HostFollowStartupLifecycleTests(unittest.TestCase):
    def test_longer_shared_guard_survives_usb_fault_and_recovery(self):
        from design_definition import DesignDefinition
        from selected_lifecycle import ownership_load_trace
        baseline=load_design();contract=baseline.contract
        contract['physical_services']['sar_timing']['startup']['assigned_guard_s']=30e-6
        design=DesignDefinition.from_documents(contract,baseline.architecture)
        result=ownership_load_trace(design.contract,direct_usb=True,design=design)
        self.assertEqual(result['status'],'completed_scoped_lifecycle')
        self.assertEqual(result['design_provenance'],design.provenance())
        usb=result['usb_extension'];recovery=usb['recovery']
        self.assertEqual(usb['exchange']['host_word_hz'],100e6)
        self.assertGreaterEqual(recovery['ready_at_s']-recovery['restart_s'],30e-6-1e-15)
        self.assertTrue(recovery['pad_released_at_fault'])
        self.assertGreater(recovery['partial_reply_bits'],0)
        self.assertLess(recovery['partial_reply_bits'],48)
        self.assertGreater(recovery['new_epoch'],recovery['old_epoch'])


class RetainedRingPowerTests(unittest.TestCase):
    def test_die_side_load_matches_independent_two_path_impedance(self):
        from baseline_envelope import retained_ring_power_screen
        r=retained_ring_power_screen();n=r['network']
        for row in r['transfer']:
            w=2j*np.pi*row['frequency_hz']
            source=n['feed_r']+w*n['feed_l']
            board=n['board_esr']+w*n['board_esl']+1/(w*n['board_c'])
            series=1/(1/source+1/board)+n['package_r']+w*n['package_l']+r['return_r_ohm']+w*r['return_l_h']
            decap=n['die_esr']+w*n['die_esl']+1/(w*n['die_c'])
            impedance=-1/(1/series+1/decap)
            self.assertAlmostEqual(row['common_ring_host_transfer_ohm'],abs(impedance),places=10)
            self.assertLess(row['kcl_residual_a'],1e-10)
            self.assertLess(row['power_residual_w'],1e-10)
        for mode in r['dc_modes']:
            current=mode['current_allocation_ma']/1000
            self.assertAlmostEqual(mode['resistive_loss_w'],current**2*(n['feed_r']+n['package_r']+r['return_r_ohm']))
            self.assertLess(abs(mode['power_residual_w']),1e-12)

    def test_metal_connected_external_sources_cannot_disagree(self):
        from baseline_envelope import retained_ring_power_screen
        from design_definition import DesignDefinition
        design=load_design();contract=design.contract;arch=design.architecture
        arch['blocks']['board']['parameters']['digital_supply_v']=3.1
        changed=DesignDefinition.from_documents(contract,arch)
        with self.assertRaisesRegex(ValueError,'one external voltage'):
            retained_ring_power_screen(changed)

TEST_DESIGN_ROLES['RetainedRingPowerTests']=('shared_design','Shared passive values and current allocations, die-side host-port correction; analytic parallel impedance and energy conservation, not physical qualification.')


class CommonRingCircuitTests(unittest.TestCase):
    def test_total_current_and_capacitance_are_not_lost(self):
        from power_distribution import from_design,mode_loads,split_rc_experiment
        design=load_design()
        for override in (None,split_rc_experiment()):
            circuit=from_design(design,local_override=override)
            self.assertAlmostEqual(circuit.capacitance_f,1e-9,places=18)
            for mode in ('rf_rx','rf_tx','wired','usb'):
                loads=mode_loads(design,mode,local_override=override)
                result=circuit.solve(0.,loads,3.3)
                n=circuit.network
                expected=3.3-sum(loads.values())*(n['feed_r']+n['package_r']+circuit.return_r)
                self.assertAlmostEqual(result['rail_v']['raw'].real,expected)
                for name,branch in circuit.branches.items():
                    self.assertAlmostEqual(result['rail_v'][name].real,expected-loads[name]*branch['r_ohm'])
                self.assertLess(abs(result['power_residual_w']),1e-11)
        with self.assertRaisesRegex(ValueError,'die side'):
            circuit.solve(1e6,{'board':.01})

    def test_generated_circuit_agrees_with_ngspice(self):
        import shutil,tempfile
        from power_distribution import verify_spice
        if not shutil.which('ngspice'):self.skipTest('ngspice required for independent circuit verification')
        with tempfile.TemporaryDirectory(prefix='common-ring-') as work:
            result=verify_spice(load_design(),work)
            self.assertEqual(len(result['cases']),8)
            self.assertTrue(all(r['ac_points']>=60 for r in result['cases']))

TEST_DESIGN_ROLES['CommonRingCircuitTests']=('shared_design','Selected common ring plus explicitly unadopted equal-capacitance RC control; DC ownership and independent SPICE/nodal agreement, not isolation qualification.')
