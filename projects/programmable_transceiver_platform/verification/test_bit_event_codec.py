import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/connected'))
from bit_event_stream import BitEventStream
from bit_event_codec import encode_records,decode_records,StreamingRecordReceiver,snapshot_records

class CodecChecks(unittest.TestCase):
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
