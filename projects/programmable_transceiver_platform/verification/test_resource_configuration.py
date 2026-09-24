"""Candidate command-word wire-format checks, not serialized integration proof."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from resource_configuration import decode_resource_word,encode_resource_word


class ResourceWordTests(unittest.TestCase):
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


class QueuedResourceTests(unittest.TestCase):
    def fixture(self):
        # Existing queue implementation, with a recording permission callback.
        # This verifies dispatch/epoch behavior, not canonical analog operation.
        import full_chip_model  # Establish existing model import paths.
        from diagnostic_tile_lifecycle import DiagnosticChip
        from resource_configuration import ResourceConfigurationCommands
        class Fixture(ResourceConfigurationCommands,DiagnosticChip):
            TILE_COMMANDS=DiagnosticChip.TILE_COMMANDS+ResourceConfigurationCommands.RESOURCE_COMMANDS
            def configure_resources(self,**settings):
                if not self.permitted:raise ValueError('Resources became busy')
                self.settings=settings
        c=Fixture();c.settings=None;c.permitted=True
        return c

    def test_wire_interface_queued_apply_and_rejection(self):
        from types import MethodType
        for rate in (.7425e9,1.485e9):
            c=self.fixture();c.wire_rate_override=rate;c.interface=None
            def configure(owner,**settings):
                if not owner.permitted:raise ValueError('Interface became busy')
                owner.interface=settings
            c.configure_wire_interface=MethodType(configure,c)
            token,apply,reply=c.submit('configure_wire_interface',c.time,c.epoch,c.rx_generation,3)
            c.advance(apply-1e-12);self.assertIsNone(c.interface)
            result=c.read_reply(token,reply)
            self.assertTrue(result['accepted'])
            self.assertEqual(c.interface['word_reference_hz'],rate/10)
            self.assertEqual(c.interface['electrical'],'dc_current_sink')
            before=dict(c.interface)
            for payload,permission,epoch in ((4,True,c.epoch),(0,False,c.epoch),(0,True,c.epoch+1)):
                c.permitted=permission
                token,_,reply=c.submit('configure_wire_interface',c.time,epoch,c.rx_generation,payload)
                self.assertFalse(c.read_reply(token,reply)['accepted'])
                self.assertEqual(c.interface,before)

    def test_apply_and_reply_times(self):
        c=self.fixture();word=encode_resource_word(engine='wire',line_rate_bps=1.62e9)
        token,apply,reply=c.submit('configure_resources',c.time,c.epoch,c.rx_generation,word)
        c.advance(apply-1e-12);self.assertIsNone(c.settings)
        c.advance(apply);self.assertEqual(c.settings,decode_resource_word(word))
        with self.assertRaises(ValueError):c.read_reply(token,apply)
        result=c.read_reply(token,reply)
        self.assertTrue(result['accepted']);self.assertEqual(result['applied_at'],apply)

    def test_reserved_word_is_rejected_at_apply(self):
        c=self.fixture()
        token,_,reply=c.submit('configure_resources',0,c.epoch,c.rx_generation,1<<31)
        self.assertFalse(c.read_reply(token,reply)['accepted']);self.assertIsNone(c.settings)

    def test_changed_permission_is_checked_at_apply(self):
        c=self.fixture();word=encode_resource_word(engine='rf')
        token,_,reply=c.submit('configure_resources',0,c.epoch,c.rx_generation,word)
        c.permitted=False
        self.assertFalse(c.read_reply(token,reply)['accepted']);self.assertIsNone(c.settings)

    def test_stale_epoch_never_reaches_callback(self):
        c=self.fixture();word=encode_resource_word(engine='rf')
        token,_,reply=c.submit('configure_resources',0,c.epoch+1,c.rx_generation,word)
        result=c.read_reply(token,reply)
        self.assertFalse(result['accepted']);self.assertIn('stale',result['reason'])
        self.assertIsNone(c.settings)


class ConverterDirectionPlanningTests(unittest.TestCase):
    def test_selected_directions_only(self):
        from full_chip_model import make_chip
        for mode in (0,1):
            for flags,offset in ((1,-1.),(2,-10e-9),(3,-10e-9),(3,10e-9)):
                c=make_chip();c.enable_reference_converter_clock();c.session.mode=mode
                tx_before=object();rx_before=object()
                c.sample_clock=tx_before;c.adc_clock=rx_before
                c.plan_local_converter_clocks(200e-9,offset,flags)
                if flags&1:self.assertIsNot(c.sample_clock,tx_before)
                else:self.assertIs(c.sample_clock,tx_before)
                if flags&2:self.assertIsNot(c.adc_clock,rx_before)
                else:self.assertIs(c.adc_clock,rx_before)
                if flags==3:
                    tx=c.sample_clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
                    rx=c.adc_clock.forecast(lambda t:3.3,maximum_slew_v_per_s=0.)
                    self.assertLess(abs(rx.time-tx.time-offset),1e-18)

    def test_invalid_plan_preserves_both_live_clocks(self):
        from full_chip_model import make_chip
        c=make_chip();c.enable_reference_converter_clock()
        a,b=object(),object();c.sample_clock=a;c.adc_clock=b
        for flags,offset in ((2,-1.),(3,-1.),(0,0.),(4,0.)):
            with self.assertRaises(ValueError):c.plan_local_converter_clocks(25e-9,offset,flags)
            self.assertIs(c.sample_clock,a);self.assertIs(c.adc_clock,b)


if __name__=='__main__':unittest.main()
