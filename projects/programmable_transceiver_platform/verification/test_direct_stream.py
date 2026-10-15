"""Independent byte-stream framing, credit and sampled-record state-machine fixtures.

Synthetic observation times test ordering and payload preservation, not shared
chip GPIO timing, physical sampling or allocated hardware queue capacity."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'system_model/architecture_fast'))
from direct_stream import Decoder, Credits, encode, word, START, END

TEST_DESIGN_ROLES = {
    'DirectTests': ('independent_fixture', 'Independent byte framing, credits, corruption and synthetic sampled-record events.'),
}

class DirectTests(unittest.TestCase):
    def test_sampled_burst_records_need_no_length_and_preserve_partial_bytes(self):
        from direct_stream import SampledBurstRecords
        for count in (1,7,8,9,31,72):
            receiver=SampledBurstRecords();cells=[]
            self.assertEqual(receiver.observe(0,None),[])
            bits=[(i+i//3)%2 for i in range(count)]
            for i,bit in enumerate(bits):cells.extend(receiver.observe(10+5*i,bit))
            self.assertFalse(receiver.closed)
            cells.extend(receiver.observe(10+5*count,None))
            self.assertFalse(receiver.closed)
            cells.extend(receiver.observe(15+5*count,None))
            self.assertTrue(receiver.closed)
            self.assertEqual([t for t,_ in cells],sorted(t for t,_ in cells))
            decoder=Decoder();records=[]
            for _,cell in cells:records.extend(decoder.feed(cell))
            self.assertEqual([value>>j&1 for kind,value,width in records if kind=='data' for j in range(width)],bits)
            self.assertEqual([kind for kind,_,_ in records if kind!='data'],['start','event'])
            self.assertFalse(decoder.active)
            self.assertEqual(receiver.count,0)

    def test_single_quiet_erasure_aborts_instead_of_splicing_a_burst(self):
        from direct_stream import SampledBurstRecords
        receiver=SampledBurstRecords();cells=[]
        for i in range(12):cells.extend(receiver.observe(i*5,i%2))
        self.assertEqual(receiver.observe(60,None),[])
        cells.extend(receiver.observe(65,1))
        self.assertTrue(receiver.closed)
        decoder=Decoder();records=[]
        for _,cell in cells:records.extend(decoder.feed(cell))
        self.assertEqual(records[-1],('abort',0,0))
        self.assertFalse(any(kind=='event' for kind,_,_ in records))
        self.assertFalse(decoder.active)

    def test_every_tail_and_streaming_length(self):
        for n in range(1,1033):
            bits=[(i*13+i//5)&1 for i in range(n)]
            d=Decoder();r=[]
            for w in encode(bits):
                self.assertEqual(d.feed(word(0)),[])
                r.extend(d.feed(w))
            self.assertEqual([v>>i&1 for k,v,c in r if k=='data' for i in range(c)],bits)
            self.assertEqual(r[0],('start',0,0));self.assertEqual(r[-1],('event',7,0))

    def test_all_single_bit_errors_fail_closed(self):
        for w in encode([1,0,1]*17):
            for bit in range(10):
                d=Decoder()
                with self.assertRaises(ValueError):d.feed(w^(1<<bit))
                self.assertTrue(d.fault)
                with self.assertRaises(ValueError):d.feed(word(START))

    def test_malformed_partial_and_order(self):
        for words in ([word(1,True)], [word(START),word(START)],
                      [word(START),word(0x13),word(END)],
                      [word(START),word(0x13),word(8,True)],
                      [word(START),word(0x13),word(1,True),word(1,True)]):
            d=Decoder()
            with self.assertRaises(ValueError):
                for w in words:d.feed(w)

    def test_credit_wrap_duplicate_and_overgrant(self):
        c=Credits()
        for n in range(100):
            c.take();c.grant((n+1)%32);c.grant((n+1)%32)
            self.assertEqual(c.available,8)
        with self.assertRaises(ValueError):c.grant(3)
        for _ in range(8):c.take()
        with self.assertRaises(ValueError):c.take()
