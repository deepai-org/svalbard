"""Independent lane-alignment arithmetic and state-machine fixtures.

Assigned delays, uncertainties and ideal readiness are test inputs, not measured
skew or a shared-design PLL/pad performance claim."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from video_alignment import Lane,compensate,launch_group


TEST_DESIGN_ROLES = {
    'ConfiguredStreamTests': ('shared_design', 'Retained shared video PLL/input/FIFO with opaque FPGA symbols and explicit host fault/recovery commands; connector pad transients and encoding are outside this fixture.'),
    'ConfiguredClockTests': ('shared_design', 'Selected PLL/configuration with explicit initial detuning; retained state through reference loss and supply failure.'),
    'AlignmentTests': ('independent_fixture', 'Assigned per-lane delays and ideal readiness test alignment arithmetic and state ordering.'),
}

class AlignmentTests(unittest.TestCase):
    def lanes(self):
        lanes=[Lane(7) for _ in range(3)]
        for l in lanes:
            l.arm(pll_locked=True,phase_qualified=True,prefilled=True)
            l.marker(100,cs_inactive=True,capture_window_valid=True)
        return lanes

    def args(self):
        delays=[8.1,19.3,43.6]
        return dict(at_reference_edge=116,epoch=7,clocks_valid=[True]*3,
                    payloads_ready=[True]*3,calibrated_delays_ui=delays,
                    compensation=compensate(delays),uncertainty_ui=[.1]*3)

    def test_coarse_and_external_fractional_compensation_align_actual_indices(self):
        lanes=self.lanes();arrivals=launch_group(lanes,**self.args())
        for t in arrivals:self.assertAlmostEqual(t,44)
        self.assertFalse(any(l.armed for l in lanes))
        with self.assertRaises(ValueError):launch_group(lanes,**self.args())

    def test_wrong_capture_edge_is_not_fixed_by_equal_frequency(self):
        lanes=self.lanes();lanes[1].captured_edge+=1
        with self.assertRaises(ValueError):launch_group(lanes,**self.args())

    def test_missing_readiness_and_late_or_uncertain_launch_rejected(self):
        for patch in ({'at_reference_edge':117},{'epoch':8},
                      {'clocks_valid':[True,False,True]},
                      {'payloads_ready':[True,True,False]},
                      {'uncertainty_ui':[.2,.2,.2]}):
            with self.assertRaises(ValueError):launch_group(self.lanes(),**(self.args()|patch))

    def test_no_unbounded_skew_buffer_or_unsafe_marker(self):
        with self.assertRaises(ValueError):compensate([8,49])
        lane=Lane(7)
        with self.assertRaises(ValueError):lane.arm(pll_locked=True,phase_qualified=False,prefilled=True)
        lane.arm(pll_locked=True,phase_qualified=True,prefilled=True)
        with self.assertRaises(ValueError):lane.marker(100,cs_inactive=False,capture_window_valid=True)
        with self.assertRaises(ValueError):lane.marker(100,cs_inactive=True,capture_window_valid=False)



class ConfiguredClockTests(unittest.TestCase):
    def test_fractional_clock_acquires_and_requalifies_without_replacing_pll(self):
        from design_definition import load_design
        from video_alignment import ConfiguredLaneClock
        for pixel in (74.25e6/1.001,148.5e6/1.001):
            c=load_design().configure(engine='wire',direction='tx',reference_hz=pixel,
                clock_source='forwarded_word',host_divider=4 if pixel<100e6 else 8)
            clock=ConfiguredLaneClock(c)
            pll=clock.pll
            self.assertFalse(clock.advance(1e-6))
            self.assertTrue(clock.advance(21e-6))
            self.assertLess(abs(clock.output_hz/c.line_rate_bps-1),50e-6)
            phase=clock.output_phase_cycles
            clock.set_source(False,22e-6)
            self.assertFalse(clock.ready)
            self.assertFalse(clock.advance(24e-6))
            self.assertGreater(clock.output_phase_cycles,phase)
            clock.set_source(True,24e-6)
            self.assertFalse(clock.advance(25e-6))
            self.assertTrue(clock.advance(45e-6))
            self.assertIs(clock.pll,pll)
            self.assertEqual(clock.source_epoch,2)
            clock.set_supply_valid(False,46e-6)
            self.assertFalse(clock.advance(48e-6))

    def test_loaded_fractional_reference_reaches_real_pll_detector(self):
        from baseline_envelope import load_design,configured_forwarded_clock
        from design_definition import Scenario
        c=load_design().configure(engine='wire',direction='tx',reference_hz=74.25e6/1.001,
            clock_source='forwarded_word',host_divider=4)
        clock=configured_forwarded_clock(c,Scenario(reference_peak_v=.5))
        self.assertFalse(clock.reference_input.report['frequency_rounding'])
        self.assertTrue(clock.advance(21e-6))
        self.assertGreater(len(clock.reference_input.windows),0)
        self.assertIs(clock.pll.reference_edge_provider,clock.reference_input)
        # At a delivered edge the detector measures the input count versus VCO
        # phase, not the nominal-reference-only error.
        clock.advance(clock.pll.next_detector)
        last=clock.pll.detector_index-1
        measured=clock.pll.error+last-c.reference_hz*clock.pll.time
        self.assertAlmostEqual(clock.pll.detector_error,measured,places=9)
        self.assertGreater(abs(clock.pll.error-clock.pll.detector_error),.01)
        self.assertEqual(clock.configuration.record(),c.record())
        with self.assertRaisesRegex(ValueError,'envelope'):
            configured_forwarded_clock(c,Scenario(reference_peak_v=1.))

    def test_reference_provider_cannot_insert_time_reversal(self):
        from design_definition import load_design
        from video_alignment import ConfiguredLaneClock
        c=load_design().configure(engine='wire',direction='tx',reference_hz=148.5e6,
            clock_source='forwarded_word',host_divider=8)
        clock=ConfiguredLaneClock(c,reference_edge_provider=lambda index:1/c.reference_hz)
        with self.assertRaisesRegex(ValueError,'strictly ordered'):clock.advance(1e-6)
        self.assertFalse(clock.ready)

    def test_edge_window_matches_independent_sinusoid_solution(self):
        import numpy as np
        from reference_input_probe import ConfiguredReferenceEdges
        # Independent single-frequency fixture: combined phasor has an exact
        # rising-threshold time, including a deliberately fractional frequency.
        e=ConfiguredReferenceEdges.__new__(ConfiguredReferenceEdges)
        e.carrier=74.25e6/1.001;e.carrier_v=.4j;e.threshold=.02
        e.tones=[(e.carrier,.025+.01j)];e.delays=[];e.phase_tones=[]
        e.window_edges=16
        e.offset=((np.arcsin(e.threshold/abs(e.carrier_v))-np.angle(e.carrier_v)-np.pi/2)%(2*np.pi))/(2*np.pi)
        roots=e._window(1)
        combined=e.carrier_v+e.tones[0][1]
        offset=((np.arcsin(e.threshold/abs(combined))-np.angle(combined)-np.pi/2)%(2*np.pi))/(2*np.pi)
        expected=(np.arange(1,18)+offset)/e.carrier
        np.testing.assert_allclose(roots,expected,rtol=0,atol=1e-18)


class ConfiguredStreamTests(unittest.TestCase):
    def test_three_loaded_lanes_stream_and_recover_one_source_fault(self):
        import math
        from baseline_envelope import load_design,configured_forwarded_clock
        from design_definition import Scenario
        from video_alignment import ConfiguredVideoStream
        from stream_codec import encode
        c=load_design().configure(engine='wire',direction='tx',reference_hz=74.25e6/1.001,
            clock_source='forwarded_word',host_divider=4)
        streams=[ConfiguredVideoStream(configured_forwarded_clock(c,Scenario(reference_peak_v=.5),
                    initial_phase_cycles=phase)) for phase in (-.2,.13,.35)]
        clocks=[s.clock.pll for s in streams];queues=[s.fifo for s in streams]
        for s in streams:self.assertTrue(s.clock.advance(21e-6))
        histories=[[] for _ in streams]
        def frame(start,sequence,count,epoch):
            payloads=[[(len(histories[lane])+j+71*lane)%1024 for j in range(count)] for lane in range(3)]
            words=[encode(1,payload,[],sequence%64,owner='wire') for payload in payloads]
            for slot in range(64):
                for lane,s in enumerate(streams):
                    s.receive_host_word(words[lane][slot],start+slot/c.h2d_word_hz,epoch)
            for history,payload in zip(histories,payloads):history.extend(payload)
            return start+64/c.h2d_word_hz
        now=frame(21e-6,0,59,0)
        edge=math.ceil((now+50e-9)*c.reference_hz)
        now=max(s.launch(edge,0) for s in streams)+1/c.h2d_word_hz
        per_frame=64*(c.line_rate_bps/10)/c.h2d_word_hz
        for n in range(1,33):
            count=math.floor(n*per_frame)-math.floor((n-1)*per_frame)
            now=frame(now,n,count,0)
        def maximum_skew(captures):
            length=min(map(len,captures))
            return max(max(captures[lane][i][0] for lane in range(3))-
                       min(captures[lane][i][0] for lane in range(3)) for i in range(length))
        self.assertLessEqual(maximum_skew([s.emitted for s in streams]),.25/c.line_rate_bps)
        first_counts=[len(s.emitted) for s in streams]
        self.assertGreater(min(first_counts),400)
        for lane,s in enumerate(streams):
            self.assertIsNone(s.fault)
            self.assertEqual([w for _,_,w in s.emitted],histories[lane][:len(s.emitted)])
            self.assertEqual(len(s.emitted)+len(s.fifo),len(histories[lane]))
            self.assertLessEqual(s.high_water,s.capacity)
        streams[1].source_presence(False,now)
        self.assertEqual(streams[1].fault,'reference_lost')
        # FPGA reacts after a whole framed status interval, not instantaneously.
        observed=now+64/c.host_word_hz
        for s in streams:s.stop(observed)
        for s in streams:s.recover(observed,1)
        self.assertTrue(any(s.flushes[-1]['discarded_words'] for s in streams))
        with self.assertRaisesRegex(ValueError,'Stale'):
            streams[0].receive_host_word(0,observed,0)
        streams[1].source_presence(True,observed+1e-6)
        for s in streams:self.assertTrue(s.clock.advance(observed+22e-6))
        histories=[[] for _ in streams]
        previous=[len(s.emitted) for s in streams]
        now=frame(observed+22e-6,0,59,1)
        edge=math.ceil((now+50e-9)*c.reference_hz)
        now=max(s.launch(edge,1) for s in streams)+1/c.h2d_word_hz
        for n in range(1,9):
            count=math.floor(n*per_frame)-math.floor((n-1)*per_frame)
            now=frame(now,n,count,1)
        for lane,s in enumerate(streams):
            new=s.emitted[previous[lane]:]
            self.assertTrue(new)
            self.assertTrue(all(epoch==1 for _,epoch,_ in new))
            self.assertEqual([word for _,_,word in new],histories[lane][:len(new)])
            self.assertIs(s.clock.pll,clocks[lane]);self.assertIs(s.fifo,queues[lane])
            self.assertIsNone(s.fault)
        self.assertLessEqual(maximum_skew([s.emitted[n:] for s,n in zip(streams,previous)]),.25/c.line_rate_bps)
        # A lost host refill must revoke output, not repeat the last symbol.
        streams[0].advance(now+2e-6)
        self.assertEqual(streams[0].fault,'underflow')
        self.assertFalse(streams[0].running)

    def test_video_ingress_overflow_is_not_hidden_by_unbounded_host_storage(self):
        from baseline_envelope import load_design
        from video_alignment import ConfiguredLaneClock,ConfiguredVideoStream
        from stream_codec import encode
        c=load_design().configure(engine='wire',direction='tx',reference_hz=148.5e6,
            clock_source='forwarded_word',host_divider=8)
        s=ConfiguredVideoStream(ConfiguredLaneClock(c))
        with self.assertRaisesRegex(ValueError,'overflow'):
            for frame in range(2):
                for slot,word in enumerate(encode(1,list(range(59)),[],frame,owner='wire')):
                    s.receive_host_word(word,(frame*64+slot)/c.h2d_word_hz,0)
        self.assertEqual(len(s.fifo),s.capacity)
        self.assertEqual(s.fault,'overflow')


if __name__=='__main__':unittest.main()
