"""Reference codec for already word/frame-aligned GPIO traffic.

Acquisition, CDC and timing are deliberately outside this codec.
"""
from dataclasses import dataclass


def crc16_bits(bits):
    """MSB-first polynomial 0x1021, initial 0xffff, no final XOR."""
    crc = 0xffff
    for bit in bits:
        top = (crc >> 15) ^ bit
        crc = (crc << 1) & 0xffff
        if top:
            crc ^= 0x1021
    return crc


def frame_crc(words):
    return crc16_bits((word >> bit) & 1 for word in words for bit in range(9,-1,-1))


def encode(slots, wire, iq, sequence, opcode=0, argument=0):
    if len(slots) != 64 or [i for i,s in enumerate(slots) if s is None] != [0,1,2,62,63]:
        raise ValueError('frame geometry')
    for source, data in [('wire',wire),('iq',iq)]:
        if len(data) > slots.count(source) or any(not 0 <= w < 1024 for w in data):
            raise ValueError('payload count/value')
    if not (0 <= sequence < 64 and 0 <= opcode < 16 and 0 <= argument < 256):
        raise ValueError('header field')
    header = len(wire) | len(iq)<<6 | sequence<<12 | opcode<<18 | argument<<22
    words = [(header >> (10*i)) & 1023 for i in range(3)] + [0]*61
    data = {'wire':iter(wire),'iq':iter(iq)}
    for i in range(3,62):
        if slots[i] in data:
            words[i] = next(data[slots[i]],0)
    trailer = frame_crc(words[:62]) | 0xa << 16
    words[62], words[63] = trailer & 1023, trailer >> 10
    return words


@dataclass(frozen=True)
class Frame:
    wire: tuple
    iq: tuple
    sequence: int
    opcode: int
    argument: int


def decode(slots, words, expected_sequence):
    if len(slots) != 64 or [i for i,s in enumerate(slots) if s is None] != [0,1,2,62,63]:
        raise ValueError('frame geometry')
    if len(words) != 64 or any(not isinstance(w,int) or not 0 <= w < 1024 for w in words):
        raise ValueError('word framing/range')
    trailer = words[62] | words[63]<<10
    if trailer >> 16 != 0xa:
        raise ValueError('trailer marker')
    if trailer & 65535 != frame_crc(words[:62]):
        raise ValueError('frame CRC')
    header = words[0] | words[1]<<10 | words[2]<<20
    counts = {'wire':header & 63, 'iq':(header>>6)&63}
    sequence = (header>>12)&63
    if sequence != expected_sequence:
        raise ValueError('frame sequence')
    for source,count in counts.items():
        if count > slots.count(source):
            raise ValueError('payload count')
    payload = {source:tuple(words[i] for i,s in enumerate(slots) if s==source)[:count]
               for source,count in counts.items()}
    return Frame(payload['wire'],payload['iq'],sequence,(header>>18)&15,(header>>22)&255)


class Receiver:
    """First error latches fault; no payload/command from that frame is released."""
    def __init__(self, slots, initial_sequence=0):
        self.slots = slots
        self.sequence = initial_sequence
        self.faulted = False

    def accept(self, words):
        if self.faulted:
            raise ValueError('receiver requires explicit retraining')
        try:
            result = decode(self.slots, words, self.sequence)
        except ValueError:
            self.faulted = True
            raise
        self.sequence = (self.sequence+1)%64
        return result
