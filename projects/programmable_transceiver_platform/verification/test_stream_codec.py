import itertools
import unittest
from stream_codec import Receiver,encode,metadata,protect,unprotect,slots

class StreamingTests(unittest.TestCase):
    def test_all_up_to_three_metadata_bit_errors(self):
        original=metadata(17,6,0,1,1)
        packed=sum(w<<(10*i) for i,w in enumerate(original))
        # 50 bits includes codeword, constant tag and guard. Detection-only:
        # no correction can miscorrect a triple error into an accepted command.
        for count in (1,2,3):
            for errors in itertools.combinations(range(50),count):
                damaged=packed^sum(1<<i for i in errors)
                if damaged>>40==packed>>40:
                    with self.assertRaises(ValueError):unprotect(damaged&((1<<40)-1))
                rx=Receiver(1)
                with self.assertRaises(ValueError):
                    for i in range(5):rx.feed((damaged>>(10*i))&1023)
                self.assertTrue(rx.fault)
    def test_all_legal_count_pairs_both_profiles(self):
        for mode in (0,1):
            plan=slots(mode)
            for wc in range(plan.count('wire')+1):
                for qc in range(plan.count('iq')+1):
                    w=list(range(wc));q=list(range(700,700+qc));rx=Receiver(mode)
                    events=[rx.feed(x) for x in encode(mode,w,q,0)]
                    self.assertEqual([e[1] for e in events if e and e[0]=='wire'],w)
                    self.assertEqual([e[1] for e in events if e and e[0]=='iq'],q)
                    self.assertTrue(all(e is None for e in events[:4]))
                    self.assertEqual(events[4],('command',(0,0)))
    def test_streams_before_frame_end_and_does_not_detect_payload_flip(self):
        f=encode(1,[123]*52,[456]*7,0);f[5]^=1
        rx=Receiver(1)
        for w in f[:5]:rx.feed(w)
        self.assertEqual(rx.feed(f[5]),('wire',122))
        self.assertFalse(rx.fault)
    def test_valid_codeword_with_bad_semantics(self):
        for args in [(53,0,0,0,0),(0,8,0,0,0),(0,0,1,0,0),(0,0,0,3,0),(0,0,0,0,1),(0,0,0,2,2)]:
            rx=Receiver(1)
            with self.assertRaises(ValueError):
                for w in metadata(*args):rx.feed(w)
            with self.assertRaises(ValueError):rx.feed(0)
            rx.reset();self.assertFalse(rx.fault)
    def test_sequence_wrap_and_lost_frame(self):
        rx=Receiver(0)
        for seq in range(130):
            for w in encode(0,[seq],[seq],seq%64):rx.feed(w)
        with self.assertRaises(ValueError):
            for w in encode(0,[],[],3):rx.feed(w)
    def test_four_bit_error_can_change_a_valid_count(self):
        # State the actual distance limit: a four-bit corruption can silently
        # turn an empty frame into one advertising one wired word.
        self.assertEqual((protect(0)^protect(1)).bit_count(),4)
        rx=Receiver(1)
        for w in metadata(1,0,0):rx.feed(w)
        self.assertEqual(rx.feed(511),('wire',511))
        self.assertFalse(rx.fault)
    def test_linear_code_basis(self):
        # Verify affine linearity on every pair of input basis vectors. Together
        # with the explicit XOR construction, error syndrome is data independent.
        zero=protect(0)
        for a in range(30):
            self.assertEqual(unprotect(protect(1<<a)),1<<a)
            for b in range(30):
                self.assertEqual(protect((1<<a)^(1<<b)),protect(1<<a)^protect(1<<b)^zero)

if __name__=='__main__':unittest.main()
