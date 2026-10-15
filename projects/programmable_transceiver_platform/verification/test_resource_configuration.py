"""Independent candidate codecs and shared-design resource admission checks.

Lifecycle tests use shared startup/host timing and legal stopped settings;
changing ownership here does not qualify RF operation or serialized commands.
"""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from resource_configuration import decode_resource_word,encode_resource_word

TEST_DESIGN_ROLES = {
    'ResourceWordTests': ('independent_fixture', 'Command-word golden vectors and independently assigned host-service arithmetic.'),
    'CurrentResourceLifecycleTests': ('shared_design', 'chip constructs the shared environment; legal resource changes and invalid requests exercise admission.'),
}


class ResourceWordTests(unittest.TestCase):
    def test_host_service_rejects_board_rate_and_queue_shortfalls(self):
        from resource_configuration import validate_host_service
        args=dict(encoding='dense',word_hz=312.5e6,board_max_word_hz=312.5e6,
                  arrival_bps=2.5e9,queue_bits=2048,burst_bits=10,
                  service_latency_s=200e-9)
        result=validate_host_service(**args)
        self.assertEqual(result['backlog_bound_bits'],510)
        self.assertFalse(result['physical_qualification'])
        for change in ({'board_max_word_hz':200e6},
                       {'service_latency_s':1e-6},
                       {'stall_fraction':.2},
                       {'encoding':'direct','word_hz':100e6}):
            with self.assertRaises(ValueError):
                validate_host_service(**dict(args,**change))

    def test_golden_words(self):
        self.assertEqual(encode_resource_word(engine='rf'),0x0c2)
        self.assertEqual(encode_resource_word(engine='wire',line_rate_bps=1.62e9),0x0d1)
        self.assertEqual(encode_resource_word(engine='wire',line_rate_bps=480e6,
            frame_words=8,pad_path='bidirectional'),0x1e5)

    def test_entire_field_space(self):
        valid=0
        for word in range(512):
            owner=word&3;rate=(word>>2)&7
            permitted=owner<3 and rate<8 and (owner==1 or (rate==0 and not word&0x120))
            if not permitted:
                with self.assertRaises(ValueError):decode_resource_word(word)
            else:
                self.assertEqual(encode_resource_word(**decode_resource_word(word)),word)
                valid+=1
        self.assertEqual(valid,136)

    def test_reserved_width_and_types(self):
        for word in (-1,512,1<<31,True,1.0):
            with self.assertRaises(ValueError):decode_resource_word(word)
        with self.assertRaises(ValueError):encode_resource_word(engine='rf',line_rate_bps=1.5e9)
        with self.assertRaises(ValueError):encode_resource_word(engine='wire',tx_enabled=1)


class CurrentResourceLifecycleTests(unittest.TestCase):
    """Current behavioral resource admission; serialized ABI remains separate."""
    def chip(self,reference_hz):
        from behavioral import BehavioralChip
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        from design_definition import load_design
        self.design=load_design()
        config=self.design.configure(engine='wire',direction='rx',reference_hz=reference_hz,host_divider=8)
        return BehavioralChip(selected_transport_assumptions(configured_environment(config)))

    def test_invalid_numeric_settings_preserve_selected_owner(self):
        chip=self.chip(1.485e9)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=1.485e9))
        before=dict(chip.resources)
        for settings in (dict(engine='rf',timing=dict(line_rate_bps=1.25e9)),
                         dict(engine='wire',timing=dict(line_rate_bps=-1.)),
                         dict(engine='rf',rf=dict(sample_hz=-1.)),
                         dict(engine='none')):
            with self.assertRaises(ValueError):chip.configure_numeric(**settings)
            self.assertEqual(chip.resources,before)
        for word in (0,512):
            with self.assertRaises(ValueError):chip.configure(word)
            self.assertEqual(chip.resources,before)

    def test_active_engine_cannot_be_reassigned_before_stop(self):
        chip=self.chip(1.25e9)
        chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=1.25e9))
        chip.start();chip.advance(chip.ready_at)
        before=dict(chip.resources)
        config=self.design.configure(engine='rf',direction='rx',reference_hz=2.4e9,
            sample_divider=256,pga_gain_db=39)
        rf=dict(sample_hz=config.sample_hz,sample_clock_source='external_lo',
            lo_hz=config.reference_hz,lo_divider=config.sample_divider,tx_cutoff_hz=3e6,rx_cutoff_hz=1.25e6)
        with self.assertRaisesRegex(ValueError,'Stop'):
            chip.configure_numeric(engine='rf',rf=rf)
        self.assertEqual(chip.resources,before)
        chip.stop()
        chip.configure_numeric(engine='rf',rf=rf)
        self.assertEqual(chip.resources['engine'],'rf')
        self.assertEqual(chip.resources['sample_hz'],config.sample_hz)


if __name__=='__main__':unittest.main()
