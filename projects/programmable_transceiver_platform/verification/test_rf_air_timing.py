"""Independent timing codecs plus shared-design logical launch/queue integration.

Ideal sample/host clocks and prescribed readiness isolate scheduling; these
checks do not qualify analog clock quality or serialized command latency.
"""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model'))
from architecture_fast.rf_air_timing import SampleLaunch,antenna_target,MODULUS
from rf_timing_command import encode_time,decode_time

TEST_DESIGN_ROLES = {
    'AirTimingTests': ('independent_fixture', 'Counter, codec and antenna-deadline arithmetic with assigned sample rates and queue observations.'),
    'AirTimingTests.test_canonical_chip_launch_uses_real_queue_and_sample_events': ('shared_design', 'configured_chip supplies shared RF settings, host timing and queue budget; ideal events isolate scheduling.'),
    'AirTimingTests.test_canonical_snapshot_carries_iq_without_pausing_stream': ('shared_design', 'configured_chip supplies shared RF settings and transport; snapshot encoding is checked independently.'),
}

class AirTimingTests(unittest.TestCase):
    def configured_chip(self, direction, divider):
        from baseline_envelope import configured_environment
        from selected_lifecycle import selected_transport_assumptions
        from design_definition import load_design
        from behavioral import BehavioralChip
        design=load_design()
        config=design.configure(engine='rf',direction=direction,reference_hz=2.4e9,
            sample_divider=divider,**({'pga_gain_db':39} if direction=='rx' else {}))
        environment=configured_environment(config)
        c=BehavioralChip(selected_transport_assumptions(environment))
        c.configure_transport('exclusive')
        # Explicit legal filter settings isolate host scheduling from filtering.
        c.configure_numeric(engine='rf',rf=dict(sample_hz=config.sample_hz,
            sample_clock_source='external_lo',lo_hz=config.reference_hz,
            lo_divider=divider,tx_cutoff_hz=3e6,rx_cutoff_hz=1.25e6,rx_filter_order=5))
        c.start();c.advance(c.ready_at)
        c.enable_rf_direction_gate(initial=direction);c.enable_rf_sample_launch()
        depth=design.contract['transport']['scheduling'][
            'egress_bits_per_source' if direction=='tx' else 'ingress_bits_per_source']
        return c,config,depth

    def test_fractional_antenna_deadline(self):
        for rate in (37.6875e6,38.625e6,4.6875e6):
            r=antenna_target(antenna_time_s=10e-6,sample_origin_s=0,sample_hz=rate,tx_delay_s=.4e-6)
            self.assertLessEqual(abs(r['error_s']),.5/rate)

    def test_wrap_late_stale_and_exact_launch(self):
        s=SampleLaunch(epoch=4,counter=MODULUS-2)
        with self.assertRaises(ValueError):s.arm(3,1)
        with self.assertRaises(ValueError):s.arm(4,MODULUS-3)
        s.arm(4,1)
        self.assertFalse(s.edge(queued_pairs=16))
        self.assertFalse(s.edge(queued_pairs=16))
        self.assertTrue(s.edge(queued_pairs=16))
        self.assertEqual(s.counter,1)
        s.edge(queued_pairs=0);self.assertFalse(s.output)

    def test_underfill_fault_and_retune_cancel(self):
        s=SampleLaunch();s.arm(0,1)
        self.assertFalse(s.edge(queued_pairs=15));self.assertEqual(s.status,'underflow')
        s.stop();s.arm(0,3);s.edge(queued_pairs=16,board_ready=False)
        self.assertFalse(s.edge(queued_pairs=16));self.assertFalse(s.output)
        s.retune(1)
        with self.assertRaises(ValueError):s.arm(0,10)

    def test_wire_format_sequence_wrap_and_corruption(self):
        for snapshot in (False,True):
            f=encode_time(65535,MODULUS-1,62,snapshot=snapshot)
            self.assertEqual(decode_time(f,62,snapshot=snapshot),dict(epoch=65535,counter=MODULUS-1))
            with self.assertRaises(ValueError):decode_time(f[::-1],62,snapshot=snapshot)
            with self.assertRaises(ValueError):decode_time(f,62,snapshot=not snapshot)
            with self.assertRaises(ValueError):decode_time(f,62,snapshot=snapshot,rf_owned=False)

    def test_snapshot_preserves_stream_counts(self):
        from stream_codec import unprotect
        counts=[59,37,38,37,38,37]
        frames=encode_time(7,123456,62,snapshot=True,iq_words=counts)
        for header,count in zip(frames,counts):
            value=unprotect(sum(w<<(10*i) for i,w in enumerate(header[:4])))
            self.assertEqual((value>>6)&63,count)
        self.assertEqual(decode_time(frames,62,snapshot=True)['counter'],123456)
        with self.assertRaises(ValueError):encode_time(7,1,0,snapshot=True,iq_words=[0]*6)

    def test_canonical_chip_launch_uses_real_queue_and_sample_events(self):
        c,config,depth=self.configured_chip('tx',256);c.arm_rf_sample_launch(encode_time(0,25,0),0)
        c.transfer(mode=1,source_hz=config.sample_hz,sample_bits=24,frames=16,depth_bits=depth,
                   directions=('rx','tx'),epoch=0,tx_prefill_bits=0,tx_source=lambda index:0)
        self.assertEqual(c.state,'active')
        self.assertEqual(len(c.rf_launch_events),1)
        self.assertEqual(c.rf_launch_events[0]['counter'],25)
        launch_time=c.rf_launch_events[0]['time_s']
        self.assertEqual(c._rf_direction_at(launch_time-1e-9),'mute')
        self.assertEqual(c._rf_direction_at(launch_time),'tx')
        self.assertEqual(c.stream['tx_out'],max(0,c.stream['sample_index']-24)*24)
        c.stop();self.assertIsNone(c.rf_launch)
        c,config,depth=self.configured_chip('tx',256);c.arm_rf_sample_launch(encode_time(0,1,0),0)
        c.transfer(mode=1,source_hz=config.sample_hz,sample_bits=24,frames=1,depth_bits=depth,
                   directions=('rx','tx'),epoch=0,tx_prefill_bits=0,tx_source=lambda index:0)
        self.assertEqual(c.state,'fault');self.assertEqual(c.stream['tx_out'],0)

    def test_canonical_snapshot_carries_iq_without_pausing_stream(self):
        from stream_codec import unprotect
        c,config,depth=self.configured_chip('rx',64)
        words=[]
        result=c.transfer(mode=1,source_hz=config.sample_hz,sample_bits=24,frames=20,depth_bits=depth,
            directions=('rx','tx'),epoch=0,tx_prefill_bits=0,rx_source=lambda i:i,
            tx_source=lambda i:0,tx_host_enable=lambda t,i:False,
            host_word_observer=lambda t,w:words.append(w))
        self.assertEqual(c.state,'active');self.assertIsNone(result['fault'])
        headers=[];sequence=None;payload=[]
        for start in range(0,len(words),64):
            header=words[start:start+5]
            if len(header)!=5:continue
            value=unprotect(sum(w<<(10*i) for i,w in enumerate(header[:4])))
            count=(value>>6)&63;op=(value>>18)&15
            if op==8:
                if sequence is None:sequence=(value>>12)&63
                headers.append(header)
                self.assertGreater(count,0)
            payload.extend(words[start+5:start+5+count])
        self.assertEqual(len(headers),6)
        self.assertEqual(decode_time(headers,sequence,snapshot=True),dict(epoch=0,counter=1))
        packed=sum(w<<(10*i) for i,w in enumerate(payload))
        self.assertEqual([(packed>>(24*i))&((1<<24)-1) for i in range(len(payload)*10//24)],list(range(len(payload)*10//24)))
        self.assertLessEqual(c.stream['high'],depth)
