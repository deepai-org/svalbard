import random
import unittest
from frame_codec import encode, decode, Receiver, crc16_bits, frame_crc
from transport_model import schedule

class CodecTests(unittest.TestCase):
    def setUp(self): self.slots = schedule({'wire':52,'iq':7})

    def test_crc_known_answer(self):
        self.assertEqual(crc16_bits((b>>i)&1 for b in b'123456789' for i in range(7,-1,-1)),0x29b1)

    def test_every_valid_count_and_command_field(self):
        rng = random.Random(31)
        for wire_count in range(53):
            for iq_count in range(8):
                wire = [rng.randrange(1024) for _ in range(wire_count)]
                iq = [rng.randrange(1024) for _ in range(iq_count)]
                seq,op,arg = rng.randrange(64),rng.randrange(16),rng.randrange(256)
                f = decode(self.slots,encode(self.slots,wire,iq,seq,op,arg),seq)
                self.assertEqual((f.wire,f.iq,f.sequence,f.opcode,f.argument),(tuple(wire),tuple(iq),seq,op,arg))

    def test_all_single_bit_errors(self):
        good = encode(self.slots,list(range(52)),[1023]*7,0,3,255)
        for position in range(640):
            bad = good.copy(); bad[position//10] ^= 1 << (position%10)
            rx = Receiver(self.slots)
            with self.subTest(position=position):
                with self.assertRaises(ValueError): rx.accept(bad)
                self.assertEqual(rx.sequence,0)
                with self.assertRaisesRegex(ValueError,'retraining'): rx.accept(good)

    def test_wrap_and_missing_frame(self):
        rx = Receiver(self.slots)
        for sequence in range(130):
            rx.accept(encode(self.slots,[],[],sequence%64))
        with self.assertRaisesRegex(ValueError,'sequence'):
            rx.accept(encode(self.slots,[],[],3))

    def test_invalid_count_with_valid_crc(self):
        words=encode(self.slots,[],[],0)
        words[0] |= 63
        trailer=frame_crc(words[:62]) | 0xa<<16
        words[62],words[63]=trailer&1023,trailer>>10
        with self.assertRaisesRegex(ValueError,'count'): decode(self.slots,words,0)

    def test_word_loss(self):
        words=encode(self.slots,[2]*52,[4]*7,0)
        with self.assertRaisesRegex(ValueError,'framing'): decode(self.slots,words[:-1],0)
        slipped=words[1:]+[0]
        with self.assertRaises(ValueError): decode(self.slots,slipped,0)

if __name__ == '__main__': unittest.main()
