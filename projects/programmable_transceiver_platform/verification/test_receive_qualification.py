"""Lifecycle requirements independent of any protocol decoder or PLL model."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from receive_qualification import ReceiveQualification


TEST_DESIGN_ROLES = {
    'ReceiveQualificationTests.test_long_acquisition_keeps_independent_holdover_and_validity': ('shared_design', 'Selected acquisition field admits extended clock observation; no data validity or longer holdover follows from the timeout.'),
    'ReceiveQualificationTests': ('independent_fixture', 'Prescribed transitions, quiet periods and analytical drift bounds test qualification logic.'),
}

class ReceiveQualificationTests(unittest.TestCase):
    def test_long_acquisition_keeps_independent_holdover_and_validity(self):
        import baseline_envelope
        from design_definition import load_design
        field=load_design().architecture['control_fields']['cdr.config']['fields']['acquisition_timeout_ui']
        self.assertEqual(field['bits'],24)
        ui=1/2.5e9
        rx=ReceiveQualification(ui_s=ui,acquisition_ui=300000,count_recovered_edges=True)
        rx.observe(0.,recovered_edge_count=0)
        waiting=rx.observe(262249*ui,transition=True,phase_qualified=False,recovered_edge_count=262249)
        self.assertEqual(waiting.state,'acquiring');self.assertFalse(waiting.valid)
        self.assertTrue(rx.observe(265000*ui,transition=True,phase_qualified=True,recovered_edge_count=265000).valid)
        self.assertEqual(rx.observe(265065*ui,recovered_edge_count=265065).fault,'unexpected_rx_loss')
        maximum=ReceiveQualification(ui_s=ui,acquisition_ui=field['maximum'],count_recovered_edges=True)
        maximum.observe(0.,recovered_edge_count=0)
        self.assertEqual(maximum.observe(field['maximum']*ui,transition=True,phase_qualified=True,
            recovered_edge_count=field['maximum']).fault,'acquisition_timeout')
        with self.assertRaises(ValueError):ReceiveQualification(ui_s=ui,acquisition_ui=field['maximum']+1)
        with self.assertRaises(ValueError):ReceiveQualification(ui_s=ui,holdover_ui=65536)

    def test_many_packet_gaps_preserve_session_without_fault(self):
        rx=ReceiveQualification(ui_s=1/480e6, quiet_source='squelch',
                                acquisition_ui=8, acquisition_failure='report_drop')
        for packet in range(100):
            t=packet*1e-3
            self.assertEqual(rx.observe(t,squelch=True).state,'quiet')
            self.assertEqual(rx.observe(t+1e-6).state,'acquiring')
            self.assertTrue(rx.observe(t+1e-6+5/480e6,transition=True,phase_qualified=True).valid)
            self.assertEqual(rx.observe(t+1e-6+10/480e6,squelch=True).state,'quiet')
            self.assertIsNone(rx.fault)

    def test_idle_is_amplitude_evidence_not_a_missing_transition(self):
        rx=ReceiveQualification(ui_s=1e-9,holdover_ui=64,quiet_source='electrical_quiet')
        rx.observe(0,transition=True,phase_qualified=True)
        self.assertEqual(rx.observe(60e-9,phase_qualified=True).state,'holdover')
        self.assertEqual(rx.observe(100e-9).fault,'unexpected_rx_loss')
        # Once unexpected loss is latched, subsequent silence cannot clear it.
        self.assertEqual(rx.observe(1, electrical_quiet=True).state,'fault')

    def test_long_legitimate_idle_and_clock_failure_are_distinct(self):
        rx=ReceiveQualification(ui_s=1e-9,quiet_source='electrical_quiet')
        rx.observe(0,transition=True,phase_qualified=True)
        self.assertEqual(rx.observe(20e-9,electrical_quiet=True).state,'quiet')
        self.assertIsNone(rx.observe(10,electrical_quiet=True).fault)
        self.assertEqual(rx.observe(11,electrical_quiet=True,clock_ok=False).fault,'clock')

    def test_bad_burst_drops_once_then_next_burst_can_acquire(self):
        rx=ReceiveQualification(ui_s=1e-9,acquisition_ui=8,
                                quiet_source='squelch',acquisition_failure='report_drop')
        rx.observe(0)
        self.assertTrue(rx.observe(9e-9).acquisition_failed)
        self.assertFalse(rx.observe(20e-9,transition=True,phase_qualified=True).valid)
        rx.observe(30e-9,squelch=True)
        self.assertTrue(rx.observe(40e-9,transition=True,phase_qualified=True).valid)
        self.assertIsNone(rx.fault)

    def test_scheduled_quiet_is_bounded_and_not_extendable(self):
        rx=ReceiveQualification(ui_s=1e-9,quiet_source='scheduled',acquisition_ui=8)
        rx.schedule_quiet(0,20,20)
        self.assertEqual(rx.observe(10e-9).state,'quiet')
        with self.assertRaises(ValueError):rx.schedule_quiet(10e-9,20,20)
        with self.assertRaises(ValueError):rx.schedule_quiet(10e-9,21,20)
        self.assertEqual(rx.observe(21e-9).state,'acquiring')
        self.assertEqual(rx.observe(40e-9).fault,'acquisition_timeout')

    def test_direction_gating_does_not_acquire_own_transmission(self):
        rx=ReceiveQualification(ui_s=1e-9)
        self.assertFalse(rx.observe(0,local_tx=True,transition=True,phase_qualified=True).valid)
        self.assertTrue(rx.observe(1e-9,transition=True,phase_qualified=True).valid)
        self.assertEqual(rx.observe(2e-9,local_tx=True,supply_ok=False).fault,'supply')

    def test_recovered_clock_counts_holdover_through_downspread(self):
        rx=ReceiveQualification(ui_s=1e-9,holdover_ui=512,count_recovered_edges=True)
        rx.observe(0,transition=True,phase_qualified=True,recovered_edge_count=0)
        # 0.5% downspread exceeds the nominal wall-time deadline at512 bits.
        end=512e-9/.995
        self.assertTrue(rx.observe(end,phase_qualified=True,recovered_edge_count=512).valid)
        self.assertEqual(rx.observe(end+1e-9,transition=True,phase_qualified=True,
                                   recovered_edge_count=513).fault,'unexpected_rx_loss')
        with self.assertRaises(ValueError):rx.observe(end+2e-9,recovered_edge_count=511)
        with self.assertRaises(ValueError):rx.observe(end+2e-9)
        clock=ReceiveQualification(ui_s=1e-9,count_recovered_edges=True)
        self.assertEqual(clock.observe(0,clock_ok=False,recovered_edge_count=0).fault,'clock')

    def test_late_transition_cannot_erase_expired_loss_deadline(self):
        rx=ReceiveQualification(ui_s=1e-9,holdover_ui=64)
        rx.observe(0,transition=True,phase_qualified=True)
        self.assertEqual(rx.observe(100e-9,transition=True,phase_qualified=True).fault,'unexpected_rx_loss')
        rx=ReceiveQualification(ui_s=1e-9,acquisition_ui=8)
        rx.observe(0)
        self.assertEqual(rx.observe(10e-9,transition=True,phase_qualified=True).fault,'acquisition_timeout')

    def test_longer_timeout_does_not_create_phase_margin(self):
        from receive_qualification import holdover_phase_bound
        args=dict(initial_error_ui=.0625,uncertainty_ui=.0625,available_ui=.25)
        self.assertTrue(holdover_phase_bound(run_ui=1024,residual_ppm=50,**args)['admissible'])
        self.assertFalse(holdover_phase_bound(run_ui=1024,residual_ppm=600,**args)['admissible'])
        self.assertFalse(holdover_phase_bound(run_ui=2500,residual_ppm=50,**args)['admissible'])

    def test_holdover_configuration_changes_allowed_run_length(self):
        rx=ReceiveQualification(ui_s=1e-9,holdover_ui=1024)
        rx.observe(0,transition=True,phase_qualified=True)
        self.assertTrue(rx.observe(400e-9,phase_qualified=True).valid)
        self.assertEqual(rx.observe(500e-9,transition=True,phase_qualified=True).state,'tracking')

    def test_modulated_drift_cannot_cancel_an_intermediate_eye_violation(self):
        from receive_qualification import modulated_holdover_phase_bound
        result = modulated_holdover_phase_bound(
            segments=[(1000, 1000, -1000)], initial_error_ui=.0625,
            uncertainty_ui=.0625, available_ui=.25)
        self.assertAlmostEqual(result['final_drift_ui'], 0)
        self.assertAlmostEqual(result['peak_drift_ui'], .25)
        self.assertFalse(result['admissible'])

    def test_modulated_constant_error_matches_existing_bound(self):
        from receive_qualification import (modulated_holdover_phase_bound,
                                            holdover_phase_bound)
        args = dict(initial_error_ui=.0625, uncertainty_ui=.0625, available_ui=.25)
        for ppm in (-50, 50, 600):
            varying = modulated_holdover_phase_bound(
                segments=[(512, ppm, ppm), (512, ppm, ppm)], **args)
            fixed = holdover_phase_bound(run_ui=1024, residual_ppm=abs(ppm), **args)
            self.assertAlmostEqual(varying['bound_ui'], fixed['bound_ui'])
            self.assertEqual(varying['admissible'], fixed['admissible'])


if __name__=='__main__':unittest.main()
