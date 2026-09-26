import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from bit_event_stream import BitEventStream
from bit_event_codec import encode_records,decode_records,StreamingRecordReceiver,snapshot_records

class CodecChecks(unittest.TestCase):
    def test_recovery_mailbox_atomicity_and_response_identity(self):
        from recovery_mailbox import RecoveryMailbox
        m=RecoveryMailbox()
        self.assertFalse(m.write(m.EPOCH,7,clocks=31))
        self.assertTrue(m.write(m.TAG,12))
        self.assertFalse(m.write(m.COMMIT,1))
        self.assertTrue(m.write(m.EPOCH,7))
        self.assertFalse(m.write(m.COMMIT,1,clocks=31))
        self.assertIsNone(m.pending)
        self.assertTrue(m.write(m.COMMIT,1,clocks=40))
        self.assertFalse(m.write(m.EPOCH,8))
        self.assertEqual(m.read(m.REPLY_STATUS),0x4000)
        self.assertIsNone(m.reference_edge())
        self.assertEqual(m.reference_edge(),(12,7,1))
        with self.assertRaises(ValueError):m.complete(11,8,0)
        m.complete(12,8,0)
        self.assertEqual(m.read(m.REPLY_STATUS),0x4000)
        m.spi_edge()
        self.assertEqual(m.read(m.REPLY_STATUS),0x4000)
        m.spi_edge()
        self.assertEqual((m.read(m.REPLY_TAG),m.read(m.REPLY_EPOCH),m.read(m.REPLY_STATUS)),(12,8,0x8000))
        for _ in range(2):
            m.write(m.EPOCH,7);m.write(m.TAG,12)
            self.assertTrue(m.write(m.COMMIT,1))
            self.assertIsNone(m.reference_edge())  # Retry cannot repeat stop.
            self.assertEqual(m.read(m.REPLY_EPOCH),8)
        m.write(m.EPOCH,8);m.write(m.TAG,12)
        self.assertFalse(m.write(m.COMMIT,3))  # Same tag, different operation.
        self.assertEqual(m.read(m.REPLY_EPOCH),8)

    def test_observed_clock_pacing_wrap_loss_and_explicit_restart(self):
        from bit_event_codec import ObservedClockPacer
        pacer=ObservedClockPacer('3.072')
        emitted=0
        for edge in range(65520,65720):
            pacer.tick(edge%65536)
            if pacer.take(30):emitted+=30
        self.assertIsNone(pacer.fault)
        self.assertGreater(emitted,500)
        self.assertLessEqual(emitted,60+197*3.072)
        for _ in range(20):pacer.tick(65719%65536)
        self.assertEqual(pacer.fault,'Reference clock timeout')
        self.assertEqual(pacer.tokens,0)
        for edge in range(100):pacer.tick(edge)
        self.assertFalse(pacer.take(1))  # Resumed clock cannot silently rearm.
        pacer.arm()
        for _ in range(3):pacer.tick(60000)
        self.assertFalse(pacer.ready)  # A stale baseline earns no burst credit.
        pacer.tick(60001);pacer.tick(60002)
        self.assertTrue(pacer.take(60))
        pacer.tick(0);pacer.tick(1)
        self.assertEqual(pacer.fault,'Reference counter discontinuity')
        self.assertEqual(pacer.tokens,0)

    def test_causal_cdr_on_pcie_compliance_pattern_and_interruption(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import causal_compliance_cdr_screen
        from protocol_signals import pcie_gen1_compliance_bits
        pattern=pcie_gen1_compliance_bits()
        self.assertEqual(len(pattern),40)
        self.assertEqual(sum(pattern),20)
        self.assertEqual([''.join(map(str,pattern[i:i+10])) for i in range(0,40,10)],
                         ['0011111010','1010101010','1100000101','0101010101'])
        result=causal_compliance_cdr_screen()
        self.assertEqual(len(result['cases']),16)
        for row in result['cases']:
            self.assertTrue(row['final_pattern_ready'] and row['final_timing_ready'])
            self.assertGreater(row['observed_complete_patterns'],100)
            self.assertEqual(row['monitor_losses'],int(row['damaged']))

    def test_cdr_detector_uses_only_receiver_time_voltage_history(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import RecoveredWordSource
        class Probe(RecoveredWordSource):
            def crossing(self,index):
                raise AssertionError('Source-indexed detector access')
            def voltage(self,time_ui):
                self.queries.append(time_ui)
                return super().voltage(time_ui)
        for phase in (-3.,.35,3.):
            source=Probe([0,1]*1000,2.5e9,phase,100.)
            source.queries=[];samples=[]
            def observe(bit,good):
                self.assertLessEqual(max(source.queries),source.detector_time_ui)
                if source.latest_crossing_ui is not None:
                    self.assertLessEqual(source.latest_crossing_ui,source.detector_time_ui)
                samples.append(source.detector_time_ui)
            source.bit_observer=observe
            for _ in range(100):source._forecast_word()
            self.assertTrue(all(b>a for a,b in zip(samples,samples[1:])))
            self.assertTrue(source.timing_qualified)
            self.assertGreater(source.detected_edges,900)
        # Changing unobserved future data cannot change already recovered words.
        a=RecoveredWordSource([0,1]*20+[0]*40,2.5e9,3.,100.)
        b=RecoveredWordSource([0,1]*20+[1]*40,2.5e9,3.,100.)
        self.assertEqual(a.forecast(0),b.forecast(0))
        self.assertEqual(a.consume(0),b.consume(0))
        self.assertEqual(a.phase,b.phase)

    def test_usb_explicit_final_pipeline_preserves_rejection(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        config=dict(clock_source='host_ddr',bits_per_cycle=16,capacity_records=8,
                    synchronizer_cycles=2,decision_cycles=3)
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),),fpga_ingress=config)
        r=usb_observed_response(**args)
        long=usb_observed_response(**dict(args,fpga_ingress=dict(config,decision_cycles=7)))
        for a,b in zip(r['cases'],long['cases']):
            clock=a['fpga_ingress']['configuration']['clock_hz']
            self.assertAlmostEqual((b['fpga_ready_s']-a['fpga_ready_s'])*clock,4.,places=8)
            self.assertGreaterEqual(b['response_latency_s'],a['response_latency_s'])
        for fault in ('sync','pid','body','eop'):
            bad=usb_observed_response(**args,packet_fault=fault)
            self.assertTrue(all(x['no_response'] and not x['delivered'] for x in bad['cases']))
        with self.assertRaises(ValueError):usb_observed_response(**dict(args,fpga_ingress=dict(config,decision_cycles=0)))

    def test_usb_host_clocked_parser_derives_clock_and_keeps_ingress_crossing(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        config=dict(clock_source='host_ddr',bits_per_cycle=16,capacity_records=8,synchronizer_cycles=2)
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),),h2d_clock_ppm=100.,fpga_ingress=config)
        r=usb_observed_response(**args)
        self.assertEqual(r,usb_observed_response(**args,split_time=True))
        for row in r['cases']:
            self.assertTrue(row['delivered'])
            actual=row['fpga_ingress']['configuration']
            self.assertEqual(actual['clock_hz'],row['h2d_word_hz']/2)
            self.assertEqual(actual['synchronizer_cycles'],2)
            self.assertEqual(row['latency_components_s']['command_crossing'],0.)
            self.assertAlmostEqual(row['fpga_ready_s']*actual['clock_hz'],round(row['fpga_ready_s']*actual['clock_hz']),places=8)
            if row['host_word_hz']==312.5e6:self.assertTrue(row['meets_budget'])
        for override in (dict(clock_hz=100e6),dict(phase_cycles=.2)):
            with self.assertRaises(ValueError):usb_observed_response(**dict(args,fpga_ingress=dict(config,**override)))
        with self.assertRaises(ValueError):usb_observed_response(**args,command_sync_cycles=2)

    def test_usb_return_command_crossing_is_not_free(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),),
                  fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=16,
                     capacity_records=8,phase_cycles=.37,synchronizer_cycles=2))
        base=usb_observed_response(**args)
        crossed=usb_observed_response(**args,command_sync_cycles=2)
        self.assertEqual(crossed,usb_observed_response(**args,command_sync_cycles=2,split_time=True))
        for a,b in zip(base['cases'],crossed['cases']):
            self.assertTrue(b['delivered'])
            self.assertFalse(b['meets_budget'])
            self.assertEqual(a['fpga_ready_s'],b['fpga_ready_s'])
            crossing=b['latency_components_s']['command_crossing']
            self.assertGreaterEqual(crossing,16/b['h2d_word_hz']-1e-15)
            self.assertLessEqual(crossing,24/b['h2d_word_hz']+1e-15)
            self.assertAlmostEqual(sum(b['latency_components_s'].values()),b['response_latency_s'])
        for stages in (-1,1.5,9):
            with self.assertRaises(ValueError):usb_observed_response(command_sync_cycles=stages)

    def test_usb_fpga_synchronization_is_charged_before_decision(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),))
        config=dict(clock_hz=100e6,bits_per_cycle=16,capacity_records=8,phase_cycles=.37)
        baseline=usb_observed_response(**args,fpga_ingress=config)
        delayed=usb_observed_response(**args,fpga_ingress=dict(config,synchronizer_cycles=2))
        self.assertEqual(delayed,usb_observed_response(**args,fpga_ingress=dict(config,synchronizer_cycles=2),split_time=True))
        for a,b in zip(baseline['cases'],delayed['cases']):
            self.assertTrue(a['delivered'] and b['delivered'])
            self.assertGreaterEqual(b['fpga_ready_s']-a['fpga_ready_s'],19.9e-9)
            self.assertGreaterEqual(b['response_latency_s'],a['response_latency_s'])
            self.assertLessEqual(b['fpga_ingress']['peak_records'],8)
        for stages in (-1,1.5,9):
            with self.assertRaises(ValueError):usb_observed_response(**args,fpga_ingress=dict(config,synchronizer_cycles=stages))

    def test_usb_processing_clock_phase_is_independent(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),))
        for phase in (0.,.37,.99):
            config=dict(clock_hz=100e6,bits_per_cycle=16,capacity_records=8,phase_cycles=phase)
            result=usb_observed_response(**args,fpga_ingress=config)
            self.assertEqual(result,usb_observed_response(**args,fpga_ingress=config,split_time=True))
            for row in result['cases']:
                self.assertEqual(row['clock_phase'],.37)
                self.assertEqual(row['playback_clock_phase'],.99)
                self.assertTrue(row['delivered'])
                if row['host_word_hz']==312.5e6:self.assertTrue(row['meets_budget'])
        for phase in (-.1,1.,float('nan')):
            with self.assertRaises(ValueError):usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=16,phase_cycles=phase))

    def test_usb_ingress_capacity_overflow_never_acknowledges(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(512,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,0.),))
        for width,capacity in ((1,8),(16,1)):
            result=usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=width,capacity_records=capacity))
            for row in result['cases']:
                self.assertFalse(row['delivered'])
                self.assertTrue(row['no_response'] and row['pad_released'])
                self.assertIn('capacity',row['packet_rejection']['reason'])
                self.assertLessEqual(row['ingress_peak_records'],capacity)
        good=usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=16,capacity_records=8))
        for row in good['cases']:
            self.assertTrue(row['delivered'])
            self.assertLessEqual(row['fpga_ingress']['peak_records'],8)

    def test_incremental_usb_parser_matches_packet_reference(self):
        from protocol_pad import USBStreamingPacket,usb_hs_packet,usb_hs_decode_packet
        for pid in (0xc3,0x4b,0xd2):
            for payload in ((b'',) if pid==0xd2 else (b'',b'\xff'*64,bytes(range(256)))):
                levels=usb_hs_packet(pid,payload)
                for width in (1,8,10,16):
                    parser=USBStreamingPacket()
                    for start in range(0,len(levels),width):parser.feed(levels[start:start+width])
                    self.assertEqual(parser.finish(),usb_hs_decode_packet(levels))
                    with self.assertRaises(ValueError):parser.feed([1])
                for index in (0,35,len(levels)-10,len(levels)-1):
                    bad=levels.copy();bad[index]^=1
                    parser=USBStreamingPacket();parser.feed(bad)
                    with self.assertRaises(ValueError):parser.finish()
        parser=USBStreamingPacket(max_payload=3)
        parser.feed(usb_hs_packet(0xc3,b'abcd'))
        with self.assertRaisesRegex(ValueError,'capacity'):parser.finish()
        self.assertLessEqual(len(parser.payload),3)

    def test_usb_parallel_work_width_changes_deadline_outcome(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,0.),),h2d_clock_ppm=-100.)
        reports=[usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=w)) for w in (8,16)]
        for narrow,wide in zip(*[r['cases'] for r in reports]):
            self.assertTrue(narrow['delivered'] and wide['delivered'])
            if narrow['host_word_hz']==312.5e6:
                self.assertFalse(narrow['meets_budget'])
                self.assertTrue(wide['meets_budget'])
                self.assertLess(wide['fpga_ingress']['tail_work_s'],narrow['fpga_ingress']['tail_work_s'])

    def test_usb_ingress_work_cannot_be_hidden_by_fixed_decision_delay(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(512,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),))
        slow=usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=1))
        fast=usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=8))
        self.assertEqual(fast,usb_observed_response(**args,fpga_ingress=dict(clock_hz=100e6,bits_per_cycle=8),split_time=True))
        for a,b in zip(slow['cases'],fast['cases']):
            self.assertTrue(a['delivered'] and b['delivered'])
            self.assertFalse(a['meets_budget'])
            self.assertGreater(a['fpga_ingress']['tail_work_s'],1e-6)
            self.assertLess(b['fpga_ingress']['tail_work_s'],60e-9)
            self.assertGreater(a['response_latency_s'],b['response_latency_s'])
            if b['host_word_hz']==312.5e6:self.assertTrue(b['meets_budget'])
        for config in ({},dict(clock_hz=0.,bits_per_cycle=8),dict(clock_hz=100e6,bits_per_cycle=1.5)):
            with self.assertRaises(ValueError):usb_observed_response(fpga_ingress=config)

    def test_usb_processing_budget_is_charged_to_deadline(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        args=dict(request_lengths=(8,),usb_data_packet=True,host_pacing=True,
                  coalesce_return=True,clock_phases=((.37,.99),),h2d_clock_ppm=100.)
        fast=usb_observed_response(**args,fpga_processing_s=40e-9)
        slow=usb_observed_response(**args,fpga_processing_s=200e-9)
        self.assertEqual(slow,usb_observed_response(**args,fpga_processing_s=200e-9,split_time=True))
        for a,b in zip(fast['cases'],slow['cases']):
            self.assertTrue(a['delivered'] and b['delivered'])
            self.assertAlmostEqual(b['latency_components_s']['fpga_decision'],200e-9,places=15)
            self.assertGreater(b['response_latency_s'],a['response_latency_s'])
            self.assertFalse(b['meets_budget'])
            if a['host_word_hz']==312.5e6:self.assertTrue(a['meets_budget'])
        for delay in (-1.,float('nan'),float('inf'),1.01e-6):
            with self.assertRaises(ValueError):usb_observed_response(fpga_processing_s=delay)

    def test_usb_response_independent_host_rates(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        for ppm in (-100.,100.):
            options=dict(request_lengths=(23,),host_pacing=True,coalesce_return=True,
                         h2d_clock_ppm=ppm,clock_phases=((0.,.99),))
            report=usb_observed_response(**options)
            self.assertEqual(report,usb_observed_response(**options,split_time=True))
            for row in report['cases']:
                self.assertTrue(row['delivered'])
                self.assertNotEqual(row['h2d_word_hz'],row['host_word_hz'])
                parts=row['latency_components_s']
                self.assertTrue(all(value>=0 for value in parts.values()))
                self.assertAlmostEqual(sum(parts.values()),row['response_latency_s'],places=15)
        for ppm in (float('nan'),float('inf'),1001.):
            with self.assertRaises(ValueError):usb_observed_response(h2d_clock_ppm=ppm)

    def test_external_usb_packet_checks(self):
        from protocol_pad import usb_crc16,usb_hs_packet,usb_hs_decode_packet
        self.assertEqual(usb_crc16(b'123456789'),0xb4c8)
        for payload in (b'',b'\xff'*16,bytes(range(32))):
            levels=usb_hs_packet(0xc3,payload)
            self.assertEqual(usb_hs_decode_packet(levels),(0xc3,payload))
            for index in (0,35,len(levels)-10,len(levels)-1):
                broken=levels.copy();broken[index]^=1
                with self.assertRaises(ValueError):usb_hs_decode_packet(broken)
        self.assertEqual(usb_hs_decode_packet(usb_hs_packet(0xd2)),(0xd2,b''))

    def test_live_usb_damaged_packet_withholds_response(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        for fault in ('sync','pid','body','eop'):
            report=usb_observed_response(request_lengths=(8,),usb_data_packet=True,
                packet_fault=fault,host_pacing=True,coalesce_return=True,
                clock_phases=((.37,.99),))
            for row in report['cases']:
                self.assertTrue(row['no_response'] and row['pad_released'])
                self.assertIsNone(row['fault'])
                self.assertGreater(row['observed_until_s']-row['request_release_s'],400e-9)

    def test_usb_retry_preserves_live_transport(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import usb_observed_response
        options=dict(request_lengths=(8,),usb_data_packet=True,packet_fault='body',
            retry_after_s=1e-6,host_pacing=True,coalesce_return=True,
            clock_phases=((.37,.99),),h2d_clock_ppm=100.)
        report=usb_observed_response(**options)
        self.assertEqual(report,usb_observed_response(**options,split_time=True))
        for row in report['cases']:
            self.assertTrue(row['delivered'])
            self.assertEqual(len(row['packet_rejections']),1)
            self.assertEqual(row['packet_rejections'][0]['reason'],'USB CRC16')
            self.assertTrue(row['retry_state']['no_response_before_retry'])
            self.assertGreater(row['retry_state']['host_words'],64)
            self.assertGreater(row['retry_state']['return_blocks'],0)

    def test_wired_recovery_independent_line_host_rates(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import raw_host_alignment_controls
        for remote,host in ((100.,-100.),(-100.,100.)):
            report=raw_host_alignment_controls(host_clock_gap=True,
                remote_clock_ppm=remote,host_clock_ppm=host)
            self.assertNotEqual(report['line_rate_bps']/8,report['host_word_hz'])
            for row in report['cases']:
                self.assertTrue(row['timeout_seen'] and row['ordered_payload_identity'])
                self.assertGreater(row['cdr_bits_during_clock_stop'],0)
                self.assertEqual(len(row['restart_discards']),1)
                self.assertGreaterEqual(row['released_frames'],32)

    def test_staged_tx_emission_observer(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import BehavioralChip,Assumptions
        source=lambda i:(37*i+5)%1024
        def run(chunks,prefill=512):
            c=BehavioralChip(Assumptions(h2d_clock_scale=1.0001))
            c.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
            c.configure_transport('exclusive');c.start();c.advance(c.ready_at)
            origin=c.time;events=[]
            observer=lambda time,word:events.append((time,word))
            for frames in chunks:
                result=c.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=frames,
                    epoch=c.epoch,directions=('tx',),tx_source=source,
                    tx_prefill_bits=prefill,host_block_words=8,host_cdc_read_hz=40e6,
                    host_cdc_phase=.37,tx_word_observer=observer)
            return c,result,events,origin
        c,r,events,origin=run((16,))
        _,parts,split,_=run((3,13))
        self.assertIsNone(r['fault']);self.assertEqual(r,parts);self.assertEqual(events,split)
        self.assertEqual([word for _,word in events],c.stream['tx_samples'])
        self.assertEqual(len(events)*10,r['tx']['consumed_bits'])
        for index,(time,_) in enumerate(events):
            self.assertAlmostEqual(time,origin+index/250e6,places=15)
        _,failed,short,_=run((16,),prefill=0)
        self.assertEqual(failed['fault'],'underflow');self.assertEqual(short,[])

    def test_emitted_tx_channel_peer(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import BehavioralChip,Assumptions,EmittedWordChannel
        source=lambda i:(37*i+5)%1024
        def run(chunks,ppm):
            c=BehavioralChip(Assumptions(h2d_clock_scale=1.0001))
            c.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
            c.configure_transport('exclusive');c.start();c.advance(c.ready_at)
            peer=EmittedWordChannel(residual_ppm=ppm)
            for frames in chunks:
                report=c.transfer(mode=1,source_hz=250e6,sample_bits=10,frames=frames,
                    epoch=c.epoch,directions=('tx',),tx_source=source,host_block_words=8,
                    host_cdc_read_hz=40e6,host_cdc_phase=.37,tx_word_observer=peer.emit)
            peer.advance(c.time)
            self.assertIsNone(report['fault']);self.assertTrue(peer.timing_qualified)
            self.assertEqual(peer.words[200:],c.stream['tx_samples'][200:len(peer.words)])
            self.assertLessEqual(peer.last_timestamp,c.time-peer.origin)
            return peer,c
        for ppm in (-100.,100.):
            whole,c=run((32,),ppm);split,_=run((3,29),ppm)
            self.assertEqual(whole.words,split.words)
            self.assertEqual(whole.phase,split.phase)
            count=len(whole.words);whole.advance(c.time+1e-6)
            self.assertLessEqual(len(whole.words),whole.emitted_words)
            self.assertLessEqual(len(whole.words)-count,1)
            with self.assertRaises(ValueError):whole.emit(whole.time+1e-6,0)

    def test_emitted_peer_idle_preserves_state_and_loses_timing(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import EmittedWordChannel
        def run(split):
            peer=EmittedWordChannel(residual_ppm=-100.)
            for n in range(256):peer.emit(n*4e-9,(37*n+5)%1024)
            self.assertTrue(peer.timing_qualified)
            before=peer.bit_index
            if split:peer.idle_until(2e-6)
            peer.idle_until(3e-6)
            self.assertFalse(peer.timing_qualified)
            self.assertGreater(peer.bit_index,before)
            self.assertEqual(peer.boundaries[-1],0.)
            for n in range(256):peer.emit(3e-6+n*4e-9,(53*n+17)%1024)
            peer.advance(3e-6+256*4e-9)
            self.assertTrue(peer.timing_qualified)
            return peer
        a=run(False);b=run(True)
        self.assertEqual(a.words,b.words);self.assertEqual(a.phase,b.phase)
        self.assertEqual(a.qualification_losses,b.qualification_losses)
        with self.assertRaises(ValueError):a.idle_until(a.time+.13e-9)

    def test_wired_delayed_rearm_recovers_frames_from_observed_bits(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import staged_wired_duplex
        for remote,host in ((100.,-100.),(-100.,100.)):
            args=dict(return_clock_gap=True,recover_tx=True,rearm_delay_s=20e-6,
                      framed_rearm=True,remote_clock_ppm=remote,host_clock_ppm=host)
            r=staged_wired_duplex(**args)
            self.assertEqual(r,staged_wired_duplex(chunks=(24,40),**args))
            self.assertTrue(r['duplex_recovered'])
            self.assertGreater(r['recovery']['tx_recovered_frames'],100)
            self.assertEqual(r['recovery']['framed_payload_errors'],0)
            self.assertGreater(r['tx_word_errors'],0)
            self.assertTrue(r['rx_ordered'])

    def test_wired_rx_continues_during_delayed_tx_rearm(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import staged_wired_duplex
        args=dict(return_clock_gap=True,recover_tx=True,rearm_delay_s=20e-6)
        r=staged_wired_duplex(**args)
        self.assertEqual(r,staged_wired_duplex(chunks=(24,40),**args))
        self.assertFalse(r['duplex_recovered'])
        self.assertEqual(r['initial_tx_fault'],'underflow')
        self.assertGreater(r['recovery']['rx_frames_during_rearm_delay'],100)
        self.assertGreater(r['recovery']['rx_bits_during_rearm_delay'],49000)
        self.assertGreater(r['recovery']['idle_bits'],99000)
        self.assertGreater(r['recovery']['tx_resumed_scored_words'],3000)
        self.assertGreater(r['tx_word_errors'],0)
        for delay in (-1.,float('nan'),101e-6):
            with self.assertRaises(ValueError):staged_wired_duplex(**dict(args,rearm_delay_s=delay))

    def test_duplex_explicit_tx_rearm_preserves_peer(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import staged_wired_duplex
        for remote,host in ((100.,-100.),(-100.,100.)):
            args=dict(remote_clock_ppm=remote,host_clock_ppm=host,
                      return_clock_gap=True,recover_tx=True)
            r=staged_wired_duplex(**args)
            self.assertEqual(r,staged_wired_duplex(chunks=(24,40),**args))
            self.assertTrue(r['duplex_recovered'])
            self.assertEqual(r['initial_tx_fault'],'underflow')
            self.assertTrue(r['recovery']['stale_tx_epoch_rejected'])
            self.assertTrue(r['recovery']['peer_lost_timing_during_idle'])
            self.assertGreater(r['recovery']['tx_resumed_scored_words'],3000)
            self.assertGreater(r['rx_released_frames'],350)
            self.assertEqual(r['tx_word_errors'],0)

    def test_staged_simultaneous_wired_paths(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import staged_wired_duplex
        for remote,host in ((100.,-100.),(-100.,100.)):
            args=dict(remote_clock_ppm=remote,host_clock_ppm=host)
            report=staged_wired_duplex(chunks=(32,),**args)
            self.assertEqual(report,staged_wired_duplex(chunks=(3,29),**args))
            self.assertGreater(report['tx_scored_words'],1000)
            self.assertEqual(report['tx_word_errors'],0)
            self.assertGreater(report['rx_released_frames'],40)
            self.assertTrue(report['rx_ordered'])
            self.assertIsNone(report['tx_flow']['fault'])

    def test_duplex_return_clock_loss_exposes_tx_reference_dependency(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import staged_wired_duplex
        for remote,host in ((100.,-100.),(-100.,100.)):
            args=dict(remote_clock_ppm=remote,host_clock_ppm=host,return_clock_gap=True)
            report=staged_wired_duplex(**args)
            self.assertEqual(report,staged_wired_duplex(chunks=(24,40),**args))
            self.assertEqual(report['tx_flow']['fault'],'underflow')
            self.assertFalse(report['duplex_recovered'])
            self.assertTrue(report['recovery']['timeout_observed'])
            self.assertGreater(report['recovery']['cdr_bits_during_halt'],1400)
            self.assertGreater(report['rx_released_frames'],report['recovery']['frames_at_restart'])
            self.assertEqual(report['tx_word_errors'],0)

    def test_reference_pacing_prevents_accumulated_host_drift(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import BehavioralChip,Assumptions
        results=[]
        for paced in (False,True):
            chip=BehavioralChip(Assumptions(h2d_clock_scale=.999))
            chip.configure_numeric(engine='wire',timing=dict(line_rate_bps=2.5e9))
            chip.configure_transport('exclusive');chip.start();chip.advance(chip.ready_at)
            results.append(chip.transfer(mode=1,source_hz=250e6,sample_bits=10,
                frames=2048,epoch=chip.epoch,directions=('tx',),
                tx_source=lambda i:(37*i+5)%1024,host_block_words=8,
                host_cdc_read_hz=40e6,host_cdc_phase=.37,tx_prefill_bits=1024,
                tx_reference_pacing=paced))
        self.assertEqual(results[0]['fault'],'underflow')
        self.assertIsNone(results[1]['fault'])
        self.assertGreater(results[1]['tx']['consumed_bits'],1_000_000)
        self.assertGreater(results[1]['tx']['minimum_bits'],0)

    def test_long_frame_interior_event_positions(self):
        # Independent source-record oracle covers every location and partial
        # width, including data after an event and event-only frames.
        for count in range(60):
            for position in range(count+1):
                for valid in (range(1,11) if position else [0]):
                    records=[('data',(i*73+7)%1024,10,0.) for i in range(count)]
                    if position:records[position-1]=('data',(1<<valid)-1,valid,0.)
                    records.insert(position,('event',(count*17+position)%256,0,0.))
                    expected=[r[:3] for r in records]
                    frame=encode_records(records,0,64)
                    self.assertEqual(decode_records(frame,0),expected)
                    receiver=StreamingRecordReceiver(64);out=[];event_slot=None
                    for slot,word in enumerate(frame):
                        emitted=receiver.feed(word);out.extend(emitted)
                        if any(r[0]=='event' for r in emitted):event_slot=slot
                    receiver.finish()
                    self.assertEqual(out,expected);self.assertEqual(event_slot,4+position)

    def test_long_snapshot_multiple_boundaries_and_wrap(self):
        stream=BitEventStream(512);expected=[]
        for index in range(130):
            for bit in range(13):stream.bit((index+bit)%2,index*20+bit)
            stream.event(index%256,index*20+13)
            expected.extend(list(stream.records)[-3:])
        receiver=StreamingRecordReceiver(64);out=[];seq=0
        while stream.records:
            frame=snapshot_records(stream,seq%64,64);seq+=1
            for word in frame:out.extend(receiver.feed(word))
        receiver.finish()
        self.assertEqual(out,[r[:3] for r in expected]);self.assertGreater(seq,64)

    def test_long_reserved_metadata_and_sticky_fault(self):
        from stream_codec import metadata
        for wc,qc,op,arg in [(60,0,0,0),(1,2,10,1),(1,1,11,1),
                             (1,0,1,1),(1,0,12,1),(1,1,0,0),(1,0,0,1)]:
            frame=metadata(wc,qc,0,op,arg)+[0]*59
            receiver=StreamingRecordReceiver(64)
            with self.assertRaises(ValueError):
                for word in frame:receiver.feed(word)
            self.assertTrue(receiver.fault)
            with self.assertRaises(ValueError):receiver.feed(0)
        # Invalid partial-word padding faults exactly where it is observed.
        frame=encode_records([('data',1,1,0),('event',2,0,0),('data',5,10,0)],0,64)
        frame[5]=2
        with self.assertRaises(ValueError):decode_records(frame,0)

    def test_all_partial_counts_and_events(self):
        for count in range(1,11):
            for event in range(256):
                records=[('data',1023,10,0),('data',(1<<count)-1,count,1),('event',event,0,1)]
                self.assertEqual(decode_records(encode_records(records,63),63),[r[:3] for r in records])
        for records in ([],[('event',0,0,0)],[('data',511,10,0)]*3):
            self.assertEqual(decode_records(encode_records(records,0),0),[r[:3] for r in records])

    def test_streaming_order_wrap_and_no_quarantine(self):
        r=StreamingRecordReceiver()
        for index in range(130):
            count=1+index%10
            records=[('data',1023,10,0),('data',(1<<count)-1,count,1),('event',index%256,0,1)]
            frame=encode_records(records,index%64)
            emissions=[r.feed(word) for word in frame]
            self.assertTrue(all(not e for e in emissions[:5]))
            self.assertEqual(emissions[5],[records[0][:3]])
            self.assertEqual(emissions[6],[records[1][:3],records[2][:3]])
            self.assertEqual(emissions[7],[])
            r.finish()
        empty=encode_records([('event',5,0,0)],130%64)
        emissions=[r.feed(word) for word in empty]
        self.assertEqual(emissions[4],[('event',5,0)])

    def test_streaming_fault_partial_payload_and_reset(self):
        r=StreamingRecordReceiver()
        frame=encode_records([('data',7,10,0),('data',1,1,0),('event',9,0,0)],0)
        for word in frame[:5]:self.assertEqual(r.feed(word),[])
        self.assertEqual(r.feed(frame[5]),[('data',7,10)])
        with self.assertRaises(ValueError):r.feed(2)
        with self.assertRaises(ValueError):r.feed(0)
        r.reset()
        for word in frame:r.feed(word)
        r.finish();r.feed(0)
        with self.assertRaises(ValueError):r.finish()
        r.reset()
        malformed=frame.copy();malformed[0]^=1
        for word in malformed[:4]:r.feed(word)
        with self.assertRaises(ValueError):r.feed(malformed[4])
        self.assertTrue(r.fault)

    def test_snapshot_boundaries_and_queue_preservation(self):
        for length in range(91):
            stream=BitEventStream(32);bits=[(i+i//3)%2 for i in range(length)]
            for i,bit in enumerate(bits):stream.bit(bit,i)
            stream.event(91,length)
            # The next burst must remain behind this boundary even if slots fit.
            stream.bit(1,length+1);stream.event(92,length+2)
            records=[];seq=0
            while stream.records:
                frame=snapshot_records(stream,seq)
                decoded=decode_records(frame,seq);records.extend(decoded)
                if any(r[0]=='event' for r in decoded):
                    self.assertEqual(decoded[-1][0],'event')
                    self.assertEqual(sum(r[0]=='event' for r in decoded),1)
                seq=(seq+1)%64
            observed=[]
            for kind,value,count in records:
                if kind=='data':observed.extend(('bit',(value>>i)&1) for i in range(count))
                else:observed.append(('event',value))
            self.assertEqual(observed,[('bit',b) for b in bits]+[('event',91),('bit',1),('event',92)])
        stream=BitEventStream();stream.records.append(('data',1,1,0))
        before=list(stream.records)
        with self.assertRaises(ValueError):snapshot_records(stream,0)
        self.assertEqual(list(stream.records),before)

    def test_protected_metadata_and_sequence(self):
        frame=encode_records([('data',3,2,0),('event',8,0,0)],0)
        for bit in range(40):
            bad=frame.copy();bad[bit//10]^=1<<(bit%10)
            with self.assertRaises(ValueError):decode_records(bad,0)
        with self.assertRaises(ValueError):decode_records(frame,1)
        with self.assertRaises(ValueError):encode_records([('data',3,2,0)],0)
        with self.assertRaises(ValueError):encode_records([('event',1,0,0),('data',0,10,1)],0)

class TrainedReturnChecks(unittest.TestCase):
    def test_clock_loss_at_every_frame_position(self):
        from bit_event_codec import TrainedRecordReceiver
        frame=encode_records([('data',7,10,0),('event',1,0,0),('data',5,10,0)],0,64)
        for stop in range(64):
            rx=TrainedRecordReceiver();time=0.
            for word in rx.training:time+=3.2e-9;self.assertEqual(rx.feed(word,time),[])
            for word in frame[:stop]:time+=3.2e-9;rx.feed(word,time)
            deadline=rx.deadline();rx.advance(deadline)
            self.assertEqual(rx.fault,'Host clock timeout');self.assertFalse(rx.locked)
            for stale in (frame[stop],rx.training[0],0):
                with self.assertRaises(ValueError):rx.feed(stale,deadline+1e-9)
            # Explicit restart plus complete preamble; never silently accepts
            # the remainder of the interrupted frame as a new epoch.
            time=deadline+10e-9;rx.arm(time)
            for word in rx.training:time+=3.2e-9;rx.feed(word,time)
            out=[]
            for word in frame:time+=3.2e-9;out.extend(rx.feed(word,time))
            self.assertEqual(out,[('data',7,10),('event',1,0),('data',5,10)])

    def test_management_delay_requires_separate_startup_window(self):
        from bit_event_codec import TrainedRecordReceiver
        # Existing management timing: 128 SPI bits at 20 MHz, two 40 MHz
        # control edges after arrival, then a separate 128-bit reply.
        apply=128/20e6+2/40e6;reply=apply+128/20e6
        rx=TrainedRecordReceiver();rx.advance(apply)
        self.assertEqual(rx.fault,'Host clock timeout')
        rx=TrainedRecordReceiver(startup_timeout_s=20e-6)
        rx.advance(apply-1e-12);self.assertIsNone(rx.fault)
        for index,word in enumerate(rx.training):rx.feed(word,apply+index*3.2e-9)
        self.assertTrue(rx.locked)
        self.assertLess(rx.last_edge,reply)  # Waiting for reply misses training.
        deadline=rx.deadline()
        self.assertAlmostEqual(deadline-rx.last_edge,100e-9)
        rx.advance(deadline);self.assertEqual(rx.fault,'Host clock timeout')
        absent=TrainedRecordReceiver(startup_timeout_s=20e-6)
        absent.advance(20e-6);self.assertEqual(absent.fault,'Host clock timeout')

    def test_training_deadline_and_clock_deadline(self):
        from bit_event_codec import TrainedRecordReceiver
        rx=TrainedRecordReceiver();time=0.
        for _ in range(1016):time+=3.2e-9;rx.feed(0,time)
        for word in rx.training:time+=3.2e-9;rx.feed(word,time)
        self.assertTrue(rx.locked)
        rx=TrainedRecordReceiver()
        for index in range(1023):rx.feed(0,(index+1)*3.2e-9)
        with self.assertRaisesRegex(ValueError,'Training timeout'):rx.feed(0,1024*3.2e-9)
        rx=TrainedRecordReceiver();rx.feed(rx.training[0],rx.deadline())
        self.assertIsNone(rx.fault)
        rx.advance(rx.deadline());self.assertEqual(rx.fault,'Host clock timeout')


class BulkReturnChecks(unittest.TestCase):
    def test_alignment_after_serialized_host_records(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import raw_host_alignment_controls
        result=raw_host_alignment_controls()
        self.assertTrue(result['alignment_after_host'])
        self.assertEqual([r['released_frames'] for r in result['cases']],[47,47,47])

    def test_reference_loss_recovery_through_ordered_records(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import raw_host_alignment_controls
        result=raw_host_alignment_controls(reference_gap=True)
        self.assertEqual([r['released_frames'] for r in result['cases']],[39,39,39])
        for row in result['cases']:
            self.assertGreater(max(row['discarded_candidate_bits']),0)
            self.assertGreater(row['maximum_status_latency_s'],0)
            self.assertEqual([good for _,good in row['reference_changes']],[True,False,True])

    def test_cdr_continues_through_connected_host_clock_recovery(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import raw_host_alignment_controls
        result=raw_host_alignment_controls(host_clock_gap=True)
        self.assertEqual([r['released_frames'] for r in result['cases']],[33,33,33])
        for row in result['cases']:
            self.assertTrue(row['timeout_seen'])
            self.assertGreater(row['cdr_bits_during_clock_stop'],0)
            self.assertEqual(row['cancelled_status'],1)
            self.assertGreater(row['restart_discards'][0]['cdc_entries'],0)

    def test_serialized_management_restart_with_queued_commands(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import TimedBulkRecordReturn
        from diagnostic_tile_lifecycle import DiagnosticChip
        class Fixture(DiagnosticChip):
            TILE_COMMANDS=DiagnosticChip.TILE_COMMANDS+('restart_raw_return',)
            def execute_management(self,operation,payload,time):
                if operation=='restart_raw_return':
                    if payload:raise ValueError('Reserved restart payload')
                    self.discarded=self.host.restart(time,receiver_already_armed=True)
                    return dict(value=self.host.epoch)
                return super().execute_management(operation,payload,time)
        for queued in (0,3):
            for phase in (0.,13e-9):
                source=BitEventStream(128);host=TimedBulkRecordReturn(source,trained=True)
                host.halt(0.)
                source.event(11,0.)
                for _ in range(23):source.bit(0,0.)
                host.receiver.startup_timeout=60e-6;host.receiver.arm(0.)
                control=Fixture(control_phase_s=phase);control.host=host
                for _ in range(queued):control.submit('status',0,control.epoch,control.rx_generation)
                token,apply,reply=control.submit('restart_raw_return',0,control.epoch,control.rx_generation)
                control.advance(apply-1e-12);self.assertEqual(host.epoch,0)
                control.advance(apply);self.assertEqual(host.epoch,1)
                self.assertGreater(control.discarded['source_records'],0)
                self.assertEqual(host.receiver.armed,0.)  # No magical receiver rearm at apply.
                source.event(22,apply)
                for i in range(1003):
                    now=apply+(i+1)/2.5e9;host.advance(now);source.bit(1,now)
                source.event(23,now);host.advance(reply)
                result=control.read_reply(token,reply)
                self.assertTrue(result['accepted']);self.assertEqual(result['value'],1)
                records=[r for _,r in host.observed]
                self.assertEqual([v for k,v,n in records if k=='event'],[22,23])
                self.assertEqual([v>>i&1 for k,v,n in records if k=='data' for i in range(n)],[1]*1003)
                self.assertTrue(host.receiver.locked)
        # The real queue's epoch fence rejects stale restart before any flush.
        source=BitEventStream();host=TimedBulkRecordReturn(source,trained=True);host.halt(0.)
        host.receiver.startup_timeout=60e-6;host.receiver.arm(0.)
        control=Fixture();control.host=host
        token,apply,reply=control.submit('restart_raw_return',0,control.epoch+1,control.rx_generation)
        result=control.read_reply(token,reply)
        self.assertFalse(result['accepted']);self.assertEqual(host.epoch,0)
        self.assertFalse(host.clock_active)

    def test_connected_clock_stop_flush_and_training(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import TimedBulkRecordReturn
        for phase in (0.,.37,.91):
            source=BitEventStream(128);host=TimedBulkRecordReturn(source,source_phase=phase,trained=True)
            source.event(11,0.)
            for i in range(3007):
                time=(i+1)/2.5e9;host.advance(time);source.bit(0,time)
            host.halt(time)
            before=(list(source.records),list(host.staged.records),host.fifo.wb,host.fifo.rb,host.frame[:])
            host.advance(time+200e-9)
            self.assertEqual(host.receiver.fault,'Host clock timeout')
            self.assertEqual(before,(list(source.records),list(host.staged.records),host.fifo.wb,host.fifo.rb,host.frame))
            cut=len(host.observed);restart=time+250e-9
            discarded=host.restart(restart)
            self.assertTrue(discarded['prepared_frame'])
            self.assertGreater(discarded['source_records']+discarded['cdc_entries']+discarded['staged_records'],0)
            self.assertGreater(discarded['partial_bits'],0)
            self.assertEqual(host.epoch,1)
            self.assertFalse(host.receiver.locked)
            source.event(22,restart)
            for i in range(2003):
                now=restart+(i+1)/2.5e9;host.advance(now);source.bit(1,now)
            source.event(23,now);host.advance(now+5e-6)
            after=[r for _,r in host.observed[cut:]]
            bits=[(value>>i)&1 for kind,value,count in after if kind=='data' for i in range(count)]
            self.assertEqual(bits,[1]*2003)
            self.assertEqual([value for kind,value,_ in after if kind=='event'],[22,23])
            self.assertTrue(host.receiver.locked);self.assertIsNone(host.receiver.fault)
            with self.assertRaises(ValueError):host.restart(now+6e-6)

    def test_packed_entry_round_trips_and_reserved_values(self):
        from bit_event_codec import pack_record_block,unpack_record_block
        for event in range(256):
            for valid in range(10):
                for value in range(1<<valid):
                    records=([('data',value,valid)] if valid else [])+[('event',event,0)]
                    self.assertEqual(unpack_record_block(pack_record_block(records)),records)
        for count in range(1,9):
            records=[('data',(i*137+1023)%1024,10) for i in range(count)]
            self.assertEqual(unpack_record_block(pack_record_block(records)),records)
        for word in [0]+[tag<<80 for tag in range(10,16)]+[(9<<80)|(10<<8),(9<<80)|(1<<22),(1<<80)|(1<<10)]:
            with self.assertRaises(ValueError):unpack_record_block(word)

    def test_same_cdc_schedule_and_reset(self):
        from block_receiver_model import BlockFIFO,RecordBlockFIFO
        from bit_event_codec import pack_record_block,unpack_record_block
        old=BlockFIFO();new=RecordBlockFIFO()
        for tick in range(1024):
            wr=tick%3==0;rd=tick%5==0;put=tick%7!=0;pop=tick%11!=0
            words=(tick%1024,) if put else None
            packed=pack_record_block([('data',tick%1024,10)]) if put else None
            a=old.step(wr_edge=wr,rd_edge=rd,words=words,pop=pop,reset=tick==511)
            b=new.step(wr_edge=wr,rd_edge=rd,words=packed,pop=pop,reset=tick==511)
            self.assertEqual(a['written'],b['written'])
            self.assertEqual(a['read'],None if b['read'] is None else tuple(r[1] for r in unpack_record_block(b['read'])))
            self.assertEqual((old.wb,old.rb,old.ws,old.rs),(new.wb,new.rb,new.ws,new.rs))

    def test_live_bulk_return_and_overload(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
        from behavioral import TimedBulkRecordReturn
        def run(rate,phase,spacing,split=False):
            source=BitEventStream(128);host=TimedBulkRecordReturn(source,source_phase=phase)
            source.event(1,0.);expected=[('event',1)];fault=None
            try:
                for i in range(65536):
                    time=(i+1)/rate
                    if split:host.advance((i+.5)/rate)
                    host.advance(time);bit=((i*137)^(i>>3)^(i>>11))&1
                    source.bit(bit,time);expected.append(('bit',bit))
                    if spacing and (i+1)%spacing==0:
                        source.event(3,time);expected.append(('event',3))
                source.event(2,time);expected.append(('event',2));host.advance(time+10e-6)
            except ValueError as error:fault=str(error)
            observed=[]
            for _,(kind,value,count) in host.observed:
                if kind=='data':observed.extend(('bit',(value>>i)&1) for i in range(count))
                else:observed.append(('event',value))
            return host,observed,expected,fault
        for rate in (1.25e9,2.5e9):
            for phase in (0.,.37,.91):
                for spacing in (0,997,4093):
                    host,out,expected,fault=run(rate,phase,spacing)
                    self.assertIsNone(fault);self.assertEqual(out,expected)
                    self.assertTrue(all(a<=b for a,b in zip(host.high_water,[128,8,67])))
        a=run(2.5e9,.37,997);b=run(2.5e9,.37,997,True)
        self.assertEqual(a[0].observed,b[0].observed)
        self.assertEqual(a[0].high_water,b[0].high_water)
        self.assertEqual(run(3.2e9,.37,0)[3],'Bit/event stream overflow')


class BitEventChecks(unittest.TestCase):
    def test_partial_word_and_event_order(self):
        for length in range(41):
            c=BitEventStream();bits=[(i*7+i//3)%2 for i in range(length)]
            for i,bit in enumerate(bits):c.bit(bit,(i+1)*1e-9)
            c.event(37,(length+1)*1e-9)
            records=list(c.records);self.assertEqual(records[-1][0:3],('event',37,0))
            decoded=[]
            for kind,value,count,time in records[:-1]:
                self.assertEqual(kind,'data');self.assertTrue(1<=count<=10)
                self.assertLess(value,1<<count)
                decoded.extend((value>>i)&1 for i in range(count))
            self.assertEqual(decoded,bits)
            self.assertEqual(c.valid_bits,0)

    def test_loaded_pad_observations_retain_partial_word(self):
        from protocol_pad import SharedWiredPad
        # Prescribed sampling clock; this checks voltage observation and packing,
        # not burst timing recovery, USB decoding or canonical scheduling.
        levels=[(i+i//4)%2 for i in range(23)]
        for role in ('host','device'):
            pad=SharedWiredPad();pad.configure('usb',role,'hs',True)
            c=BitEventStream();ui=1/480e6
            for i,level in enumerate(levels):
                pad.advance(i*ui);pad.drive(peer='J' if level else 'K')
                pad.advance((i+.5)*ui);observation=pad.observe()
                self.assertFalse(observation['squelch'])
                c.bit(int(observation['j']),pad.time)
            pad.advance(len(levels)*ui);pad.drive()
            pad.advance((len(levels)+.5)*ui)
            self.assertTrue(pad.observe()['squelch'])
            c.event(7,pad.time)
            records=list(c.records)
            self.assertEqual([r[2] for r in records],[10,10,3,0])
            observed=[(r[1]>>i)&1 for r in records[:-1] for i in range(r[2])]
            self.assertEqual(observed,levels)

    def test_atomic_overflow_and_sticky_fault(self):
        c=BitEventStream(2);c.event(1,0);c.bit(1,1)
        before=(list(c.records),c.word,c.valid_bits,c.time)
        with self.assertRaises(ValueError):c.event(2,2)
        self.assertEqual(before,(list(c.records),c.word,c.valid_bits,c.time))
        with self.assertRaises(ValueError):c.pop()
        with self.assertRaises(ValueError):c.bit(0,3)
        c.reset();self.assertIsNone(c.pop());self.assertFalse(c.fault)

    def test_full_word_overflow(self):
        c=BitEventStream(2);c.event(0,0);c.event(1,0)
        for i in range(9):c.bit(1,i)
        with self.assertRaises(ValueError):c.bit(1,9)
        self.assertEqual((c.word,c.valid_bits),(511,9))

    def test_consumer_drain_and_observation_validation(self):
        c=BitEventStream(2)
        for i in range(100):
            c.bit(i%2,i);c.event(i%256,i)
            self.assertEqual(c.pop()[:3],('data',i%2,1))
            self.assertEqual(c.pop()[:3],('event',i%256,0))
        for time in (98,float('nan'),float('inf')):
            with self.assertRaises(ValueError):c.event(0,time)
        with self.assertRaises(ValueError):c.bit(True,100)
        with self.assertRaises(ValueError):c.event(256,100)
        self.assertFalse(c.fault)



if __name__=='__main__':unittest.main()
