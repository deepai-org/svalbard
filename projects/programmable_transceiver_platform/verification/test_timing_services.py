"""Independent timing-service state machines and analytical examples.

Prescribed readiness, rates and deadlines exercise ordering and rejection.
These examples do not establish the intended chip settling or turnaround time."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from timing_services import WarmHop,gain_feedback_bound,cdr_holdover_error

TEST_DESIGN_ROLES = {
    'TimingServicesTests': ('independent_fixture', 'Assigned readiness, loop rates, delays and independent timing-budget controls.'),
}

class TimingServicesTests(unittest.TestCase):
    def test_cold_cdr_acceptance_rejects_late_acquisition_and_queue_fault(self):
        import copy
        from unittest.mock import patch
        import baseline_envelope as baseline
        import selected_revision_check as check
        design=baseline.load_design()
        case=dict(heldout_errors=0,heldout_policy_valid_fraction=1.,
            heldout_qualified_fraction=1.,qualification_losses=0,
            heldout_free_run_residual_abs_ppm_quantiles=[0.,0.,1.],
            first_qualified_bit=2000,periodic_clock_controller=dict(observation_link=dict(
                fault=None,peak_chip_queue_bits=80,queue_capacity_bits=1024)))
        def run(changes):
            candidate=copy.deepcopy(case);candidate.update(changes)
            report=dict(result=dict(cases=[candidate]),prototype_controls=dict(acquisition_ui=1000000),model_assumptions={})
            with patch.object(check,'configured_phase_bank_tracking_screen',return_value=report) as factory:
                result=check.selected_cdr_tracking_screen(design,cold=True)
            self.assertEqual(factory.call_args.kwargs['initial_local_offset_ppm'],0.)
            return result
        self.assertTrue(run({})['selected_tracking_pass'])
        for acquisition in (None,1000001):
            self.assertFalse(run(dict(first_qualified_bit=acquisition))['selected_tracking_pass'])
        broken=dict(observation_link=dict(fault='observation_overflow',peak_chip_queue_bits=80,queue_capacity_bits=1024))
        self.assertFalse(run(dict(periodic_clock_controller=broken))['selected_tracking_pass'])

    def test_periodic_clock_is_learned_from_past_observations(self):
        import numpy as np
        from timing_services import fit_periodic_clock,periodic_clock_period_prediction
        rng=np.random.default_rng(18);n=np.arange(400000);rate=2.5e9
        periods=1/(1+(-80-4700*(1-abs(2*((n*31300/rate+.371)%1)-1)))*1e-6)
        edges=np.r_[0,np.cumsum(periods)]  # Independent per-cycle source integration.
        indices=3000+np.r_[0,np.cumsum(2048+rng.integers(0,101,127))]
        observations=np.c_[indices,edges[indices]+rng.normal(0,.002,128)]
        fit=fit_periodic_clock(observations,line_hz=rate)
        self.assertTrue(fit['observed_phase_validation_pass'])
        self.assertFalse(fit['qualified'])  # A waveform fit cannot confer readiness.
        future=np.arange(270000,390000)
        errors=abs(periodic_clock_period_prediction(fit,future)/periods[future]-1)*1e6
        self.assertLess(max(errors),1.)
        changed=observations.copy()
        changed[96:,1]+=(changed[96:,0]-changed[95,0])*200e-6
        rejected=fit_periodic_clock(changed,line_hz=rate)
        self.assertFalse(rejected['observed_phase_validation_pass'])
        for key in ('period_ui','phase_cycles','offset_ppm','depth_ppm','intercept_ui'):
            self.assertEqual(fit[key],rejected[key])  # Held-out data never tune the fit.
        from timing_services import PeriodicClockController
        import copy
        controller=PeriodicClockController(rate,32e-6)
        # Feed all received observations; the controller owns its decimation.
        for count,edge in observations:
            controller.observe(int(count),float(edge))
        self.assertEqual(controller.state,'processing')
        before=copy.copy(controller)
        self.assertEqual(controller.step(340000,controller.ready_after_ui-.001),(False,None,0.))
        activated,period,_=controller.step(340001,controller.ready_after_ui)
        self.assertTrue(activated);self.assertGreater(period,1.)
        self.assertEqual(before.state,'processing')
        probe=np.linspace(fit['origin_cycle'],fit['origin_cycle']+2*fit['period_ui'],10000)
        periods=periodic_clock_period_prediction(fit,probe)
        self.assertLessEqual(max(abs(np.diff(periods)/np.diff(probe))),controller.period_slew_bound()*(1+1e-8))
        # A newly observed phase mismatch revokes control immediately and latches.
        controller.observe(340002,1e9)
        self.assertEqual(controller.state,'invalid')
        self.assertEqual(controller.step(340003,1e9),(False,None,0.))
        self.assertEqual(len(controller.observations),128)
        settings=dict(word_hz=100e6,latency_s=60e-9,queue_bits=160,coefficient_return_s=652.5e-9)
        distributed=PeriodicClockController(rate,32e-6,settings)
        for count,edge in observations:
            distributed.observe(int(count),float(edge),float(edge)+.5)
            distributed.step(int(count)+512,float(edge)+512)
        self.assertEqual(distributed.state,'processing')
        self.assertEqual(len(distributed.link.fpga_observations),128)
        self.assertLessEqual(distributed.link.peak_queue_bits,160)
        self.assertAlmostEqual((distributed.ready_after_ui-distributed.link.last_delivery_ui)/rate,32e-6+652.5e-9)
        from timing_services import encode_clock_coefficients,decode_clock_coefficients
        command=distributed.pending_coefficients
        self.assertEqual(len(command),64)
        local=decode_clock_coefficients(command,0)
        self.assertLess(max(abs(periodic_clock_period_prediction(local,future)-
                               periodic_clock_period_prediction(distributed.fit,future)))*1e6,.001)
        for malformed in (command[:-1],bytes([2])+command[1:],command[:3]+bytes([1])+command[4:]):
            with self.assertRaises(ValueError):decode_clock_coefficients(malformed,0)
        with self.assertRaisesRegex(ValueError,'epoch'):decode_clock_coefficients(command,1)
        with self.assertRaises(ValueError):encode_clock_coefficients(dict(distributed.fit,depth_ppm=7000),0)
        stale=distributed.clone();stale.link.epoch=1
        self.assertEqual(stale.step(343001,stale.ready_after_ui),(False,None,0.))
        self.assertEqual(stale.invalid_reason,'coefficient_command')
        self.assertIsNone(stale.local_fit)
        self.assertIsNone(distributed.local_fit)  # No partial application before arrival.
        self.assertEqual(distributed.step(343000,distributed.ready_after_ui-.001),(False,None,0.))
        self.assertTrue(distributed.step(343001,distributed.ready_after_ui)[0])
        self.assertFalse(distributed.local_validated)
        self.assertEqual(distributed.local_fit,local)
        distributed.observe(343002,float(edges[343002]))
        self.assertTrue(distributed.local_validated)
        with self.assertRaisesRegex(ValueError,'two longest'):
            fit_periodic_clock(observations/4,line_hz=rate)
        with self.assertRaisesRegex(ValueError,'128 ordered'):
            fit_periodic_clock(observations[:-1],line_hz=rate)

    def test_clock_observation_link_is_finite_quantized_and_epoch_bound(self):
        from timing_services import encode_clock_observation,decode_clock_observation,PeriodicObservationLink,PeriodicClockController
        record=encode_clock_observation(2050,2055.0045097,7)
        self.assertEqual(len(record),10)
        cycle,edge=decode_clock_observation(record,7)
        self.assertEqual(cycle,2050)
        self.assertLessEqual(abs(edge-2055.0045097),.5/(1<<16))
        with self.assertRaisesRegex(ValueError,'epoch'):decode_clock_observation(record,8)
        with self.assertRaises(ValueError):encode_clock_observation(1<<24,0.,7)
        with self.assertRaises(ValueError):encode_clock_observation(0,float(1<<24),7)
        settings=dict(word_hz=100e6,latency_s=60e-9,queue_bits=160,coefficient_return_s=652.5e-9,epoch=7)
        original=PeriodicClockController(2.5e9,32e-6,settings);predicted=original.clone()
        predicted.observe(2050,2055.0045097,2055.5)
        link=predicted.link;finish=link.pending[0][0]
        link.advance(finish-.001)
        self.assertEqual(link.fpga_observations,())
        predicted.step(2500,finish)
        self.assertEqual(len(predicted.observations),1)
        self.assertEqual(original.link.pending,())
        self.assertEqual(original.observations,())
        self.assertEqual(link.peak_queue_bits,80)
        self.assertAlmostEqual((finish-2055.5)/2.5e9,160e-9)
        framed=PeriodicObservationLink(2.5e9,**dict(settings,word_bits=10,word_hz=312.5e6,latency_s=442.4e-9))
        framed.enqueue(2048,2048.1,2048.5)
        self.assertAlmostEqual((framed.pending[0][0]-2048.5)/2.5e9,468e-9)
        framed.advance(framed.pending[0][0])
        self.assertEqual(len(framed.fpga_observations),1)

        blocked=PeriodicObservationLink(2.5e9,**dict(settings,latency_s=1e-3,queue_bits=80))
        blocked.enqueue(2048,2048.1,2048.5);blocked.enqueue(4096,4096.1,4096.5)
        self.assertEqual(blocked.fault,'observation_overflow')
        self.assertEqual(len(blocked.pending),1)
        stale=PeriodicObservationLink(2.5e9,**settings)
        stale.enqueue(2048,2048.1,2048.5);stale.epoch=8;stale.advance(3000)
        self.assertEqual(stale.fault,'observation_epoch')
        self.assertEqual(stale.fpga_observations,())
        controller=PeriodicClockController(2.5e9,32e-6,dict(settings,latency_s=1e-3,queue_bits=80))
        controller.observe(2048,2048.1,2048.5)
        controller.observe(4096,4096.1,4096.5)
        self.assertEqual(controller.step(4097,4097.),(False,None,0.))
        self.assertEqual(controller.state,'invalid')
        self.assertEqual(controller.invalid_reason,'observation_overflow')
        self.assertFalse(controller.local_validated)
        # Draining the queue later must not silently restart a rejected epoch.
        self.assertEqual(controller.step(3000000,3000000.),(False,None,0.))
        self.assertEqual(controller.state,'invalid')

    def hop(self):
        h=WarmHop(7)
        h.begin(host_stable=True,context_loaded=True,muted=True,queues_discarded=True)
        return h

    def test_source_settling_and_epoch_must_all_precede_launch(self):
        h=self.hop()
        with self.assertRaises(ValueError):h.launch(1e-6,8)
        self.assertFalse(h.observe(35e-6,source_qualified=True))
        self.assertFalse(h.observe(40e-6,source_qualified=True,samples_flushed=True,gain_settled=True))
        self.assertTrue(h.observe(49e-6,source_qualified=True,samples_flushed=True,gain_settled=True,epoch_ack=True,prefilled=True))
        with self.assertRaises(ValueError):h.launch(49e-6,7)
        h.launch(50e-6,8);self.assertTrue(h.output)

    def test_missing_or_late_source_never_becomes_ready(self):
        for kwargs in ({},{'host_ok':False},{'supply_ok':False},{'source_qualified':True}):
            h=self.hop();self.assertFalse(h.observe(51e-6,**kwargs));self.assertEqual(h.state,'fault')

    def test_planned_clock_absence_only_during_retune(self):
        h=self.hop();self.assertFalse(h.observe(20e-6))
        h.observe(30e-6,source_qualified=True)
        h.observe(31e-6);self.assertEqual(h.state,'fault')

    def test_gain_loop_includes_two_real_transport_paths(self):
        r=gain_feedback_bound();self.assertLess(r['total_s'],3e-6)
        self.assertGreater(r['total_s'],2.5e-6)
        self.assertGreater(gain_feedback_bound(settling_s=4e-6)['total_s'],6e-6)
        self.assertGreater(gain_feedback_bound(sample_hz=4.7e6)['total_s'],5e-6)

    def test_ssc_slew_changes_holdover_acceptance(self):
        self.assertTrue(cdr_holdover_error(line_hz=2.5e9,run_ui=20)['admissible'])
        self.assertTrue(cdr_holdover_error(line_hz=1.485e9,run_ui=1024,frequency_slew_ppm_s=0)['admissible'])
        self.assertFalse(cdr_holdover_error(line_hz=1.485e9,run_ui=1024)['admissible'])

    def test_tracking_slew_across_rates_and_loop_bounds(self):
        from timing_services import ssc_tracking_screen
        for rate in (1.25e9,1.485e9,1.5e9,1.62e9,2.5e9):
            for loop in (2.5e6,7.5e6):
                self.assertTrue(ssc_tracking_screen(line_hz=rate,loop_hz=loop)['admissible'])
        self.assertFalse(ssc_tracking_screen(loop_hz=100e3)['admissible'])
        with self.assertRaises(ValueError):ssc_tracking_screen(static_ppm=-2000)

    def test_realistic_hop_gaps_not_full_slot_assumption(self):
        from timing_services import hop_admission
        self.assertTrue(hop_admission(68e-6,312.5e-6)['admissible'])
        self.assertTrue(hop_admission((126+2790)*1e-6,3125e-6)['admissible'])
        self.assertFalse(hop_admission(600e-6,625e-6)['admissible'])

    def test_training_deadline_includes_settling_and_reserved_sync(self):
        from timing_services import acquisition_admission
        self.assertTrue(acquisition_admission(8e-6,reserve_s=2e-6,rounds=2)['admissible'])
        self.assertTrue(acquisition_admission(4e-6,reserve_s=1e-6)['admissible'])
        self.assertFalse(acquisition_admission(8e-6,reserve_s=2e-6,rounds=2,settling_s=2e-6)['admissible'])
        self.assertTrue(acquisition_admission(128e-6,reserve_s=32e-6,rounds=2,sample_hz=4.7e6,settling_s=5e-6)['admissible'])

    def test_gain_admission_rejects_unrepresentable_recovery_gap(self):
        from timing_services import acquisition_admission
        r=acquisition_admission(20e-6,reserve_s=2e-6,settling_s=3e-6)
        self.assertGreater(r['remaining_s'],0.)
        self.assertEqual(r['invalid_pairs_per_update'],137)
        self.assertFalse(r['status_count_fits'])
        self.assertFalse(r['admissible'])
