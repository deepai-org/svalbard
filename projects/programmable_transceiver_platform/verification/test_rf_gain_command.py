"""Independent gain-command codecs plus shared-design queue/status integration.

The ClientBench case derives transport from the shared design, then injects
sample-index data and prescribed 22/28-sample invalid intervals to check gap
accounting. Those intervals do not demonstrate the analog PGA settling time.
"""
import unittest
from rf_gain_command import encode_gain,decode_gain,LNA,PGA

TEST_DESIGN_ROLES = {
    'GainCommandTests': ('independent_fixture', 'Gain/epoch codecs and sample-index corruption examples with assigned frames and counts.'),
    'GainCommandTests.test_chip_gain_status_uses_actual_queue_discard_and_sample_indices': ('shared_design', 'ClientBench receives one explicit snapshot; prescribed settling intervals and sample-index payloads isolate queue/gap accounting.'),
}

class GainCommandTests(unittest.TestCase):
    def test_all_atomic_gain_pairs_and_invalid_sample_status(self):
        for lna in LNA:
            for pga in PGA:
                c=decode_gain(encode_gain(lna,pga,63),63)
                self.assertEqual((c['lna_db'],c['pga_db']),(lna,pga))
                r=decode_gain(encode_gain(lna,pga,0,invalid_pairs=16,iq_words=48,status=True),0,status=True)
                self.assertEqual((r['invalid_pairs'],r['iq_words']),(16,48))

    def test_extended_status_preserves_gains_and_command_reserved_bit(self):
        for lna in LNA:
            for gap in (63,64,67,127):
                header=encode_gain(lna,42,0,invalid_pairs=gap,status=True)
                result=decode_gain(header,0,status=True)
                self.assertEqual((result['lna_db'],result['invalid_pairs']),(lna,gap))
                with self.assertRaises(ValueError):decode_gain(header,0)

    def test_corrupt_stale_or_wrong_owner_never_applies(self):
        header=encode_gain(10,24,4)
        for bit in range(50):
            bad=header.copy();bad[bit//10]^=1<<(bit%10)
            with self.assertRaises(ValueError):decode_gain(bad,4)
        with self.assertRaises(ValueError):decode_gain(header,3)
        with self.assertRaises(ValueError):decode_gain(header,4,rf_owned=False)
        with self.assertRaises(ValueError):encode_gain(10,24,4,invalid_pairs=128,status=True)

    def test_serialized_gain_gap_restarts_packing_without_shifting_samples(self):
        from stream_codec import encode
        from rf_gain_command import GainSampleReceiver
        def words(values,count):
            bits=sum(v<<(24*i) for i,v in enumerate(values))
            return [(bits>>(10*i))&1023 for i in range(count)]
        old=encode(1,[],words([0x123456,0xabcdef,0x654321],7),0,owner='iq')
        payload=words([0x010203,0x987654,0x111111],6)
        new=encode_gain(20,42,1,invalid_pairs=3,iq_words=6,status=True)+payload+[0]*53
        receiver=GainSampleReceiver(first_sample=100)
        events=[event for word in old+new if (event:=receiver.feed(word)) is not None]
        samples=[e for e in events if e['kind']=='sample']
        self.assertEqual([e['sample_index'] for e in samples],[100,101,105,106])
        self.assertEqual([e['value'] for e in samples],[0x123456,0xabcdef,0x010203,0x987654])
        self.assertEqual([e['count'] for e in events if e['kind']=='gap'],[3])
        # A zero gap cannot account for the discarded partial old pair.
        receiver=GainSampleReceiver()
        for word in old:receiver.feed(word)
        with self.assertRaisesRegex(ValueError,'Partial old pair'):
            for word in encode_gain(20,42,1,status=True):receiver.feed(word)
        self.assertTrue(receiver.fault)

    def test_gain_status_is_opt_in_and_corruption_never_advances_index(self):
        from stream_codec import Receiver
        from rf_gain_command import GainSampleReceiver
        header=encode_gain(20,42,0,invalid_pairs=46,status=True)
        legacy=Receiver(1,owner='iq')
        with self.assertRaises(ValueError):
            for word in header:legacy.feed(word)
        for bit in range(50):
            receiver=GainSampleReceiver(100)
            bad=header.copy();bad[bit//10]^=1<<(bit%10)
            with self.assertRaises(ValueError):
                for word in bad:receiver.feed(word)
            self.assertEqual(receiver.next_sample,100)
            self.assertTrue(receiver.fault)

    def test_chip_gain_status_uses_actual_queue_discard_and_sample_indices(self):
        from wifi_client_exchange import ClientBench
        from design_definition import load_design
        from rf_gain_command import GainSampleReceiver
        from rf_timing_command import decode_time
        from stream_codec import unprotect,metadata
        design=load_design()
        queues=design.contract['transport']['scheduling']
        queue_limit=min(queues['ingress_bits_per_source'],queues['egress_bits_per_source'])
        for phase in range(8):
            b=ClientBench(design=design);wire=[]
            b.args['rx_source']=lambda index:index
            b.args['host_word_observer']=lambda time,word:wire.append(word)
            b.advance(1e-6)
            with self.assertRaisesRegex(ValueError,'completed snapshot'):
                b.chip.arm_rf_gain_transition(encode_gain(20,42,0),0,
                                             commit_sample=100,settling_samples=22)
            b.advance(4e-6)
            commit=b.chip.stream['sample_index']+phase+1
            b.chip.arm_rf_gain_transition(encode_gain(20,42,0),0,
                                         commit_sample=commit,settling_samples=22)
            with self.assertRaisesRegex(ValueError,'no pending update'):
                b.chip.arm_rf_gain_transition(encode_gain(20,27,1),1,
                                             commit_sample=commit+1,settling_samples=28)
            if phase%2:b.advance(5e-6)
            b.advance(7e-6)
            commit=b.chip.stream['sample_index']+phase+1
            b.chip.arm_rf_gain_transition(encode_gain(20,27,1),1,
                                         commit_sample=commit,settling_samples=28)
            b.advance(10e-6)
            receiver=GainSampleReceiver();events=[];snapshots=[]
            for start in range(0,len(wire)-63,64):
                frame=wire[start:start+64]
                h=unprotect(sum(frame[j]<<(10*j) for j in range(4)))
                if (h>>18)&15==8:
                    snapshots.append(frame[:5])
                for word in frame:
                    event=receiver.feed(word)
                    if event is not None:
                        events.extend(event['samples'] if event['kind']=='snapshot' else [event])
            self.assertEqual(len(snapshots),6)
            first=unprotect(sum(snapshots[0][j]<<(10*j) for j in range(4)))
            origin=decode_time(snapshots,(first>>12)&63,snapshot=True)['counter']
            samples=[e for e in events if e['kind']=='sample']
            self.assertGreater(len(samples),200)
            for sample in samples:self.assertEqual(sample['value']+origin,sample['sample_index'])
            gaps=[e for e in events if e['kind']=='gap']
            self.assertEqual(len(gaps),2)
            chip_events=b.chip.stream['rf_gain_status_events']
            self.assertEqual([e['count'] for e in gaps],[e['gap'] for e in chip_events])
            self.assertEqual([e['first_sample'] for e in gaps],[e['first_invalid']+origin for e in chip_events])
            self.assertLessEqual(b.chip.stream['high'],queue_limit)

    def test_incomplete_snapshot_cannot_release_buffered_samples(self):
        from rf_gain_command import GainSampleReceiver
        from rf_timing_command import encode_time
        from stream_codec import encode
        receiver=GainSampleReceiver()
        headers=encode_time(0,100,0,snapshot=True,iq_words=[3]*6)
        for word in headers[0]+[0]*59:
            self.assertIsNone(receiver.feed(word))
        self.assertEqual(len(receiver.snapshot_samples),1)
        with self.assertRaisesRegex(ValueError,'Snapshot interrupted'):
            for word in encode(1,[],[],1,owner='iq'):receiver.feed(word)
        self.assertTrue(receiver.fault)

    def test_full_epoch_has_no_truncated_or_mixed_phase_ack(self):
        from rf_gain_command import encode_epoch,decode_epoch
        for epoch in (0,63,64,4095,4096,65535):
            for phase in ('arm','ready','ack'):
                header=encode_epoch(epoch,17,phase)
                self.assertEqual(decode_epoch(header,17,phase),epoch)
                with self.assertRaises(ValueError):decode_epoch(header,18,phase)
                with self.assertRaises(ValueError):decode_epoch(header,17,'ready' if phase!='ready' else 'ack')
