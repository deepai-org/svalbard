"""Generic 10-pin SDR burst transport. No USB parsing, CRC, or automatic reply.

Single-bit parity is a link error screen, not error correction. Physical capture,
clock watchdogs and shared epoch reset remain implementation obligations.
"""
IDLE, START, END, ABORT = 0, 1, 2, 3


def word(value, data=False):
    if type(value) is not int or not 0 <= value < 256:
        raise ValueError('eight-bit value')
    payload = value | (int(data) << 8)
    return payload | ((payload.bit_count() & 1) << 9)


def unpack(value):
    if type(value) is not int or not 0 <= value < 1024 or value.bit_count() & 1:
        raise ValueError('word width/parity')
    return bool(value & 256), value & 255


def encode(bits):
    bits = list(bits)
    if not bits or any(type(b) is not int or b not in (0, 1) for b in bits):
        raise ValueError('nonempty binary burst')
    out = [word(START)]
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            out.append(word(0x10 + len(chunk)))
        out.append(word(sum(b << j for j, b in enumerate(chunk)), True))
    return out + [word(END)]


class Decoder:
    def __init__(self):
        self.active = self.partial = self.must_end = self.fault = False

    def feed(self, value):
        if self.fault:
            raise ValueError('sticky transport fault')
        try:
            data, value = unpack(value)
            if not data and value == IDLE:
                return []
            if not data and 0x40 <= value < 0x60:
                return [('credit', value & 31, 0)]
            if not data and value == ABORT:
                self.active = self.partial = self.must_end = False
                return [('abort', 0, 0)]
            if data:
                if not self.active or self.must_end:
                    raise ValueError('data outside burst/after partial')
                count = self.partial or 8
                if value >= 1 << count:
                    raise ValueError('nonzero partial padding')
                self.must_end = bool(self.partial)
                self.partial = False
                return [('data', value, count)]
            if value == START and not self.active:
                self.active = True
                return [('start', 0, 0)]
            if value == END and self.active and not self.partial:
                self.active = self.must_end = False
                return [('event', 7, 0)]
            if 0x11 <= value <= 0x17 and self.active and not self.partial and not self.must_end:
                self.partial = value - 0x10
                return []
            raise ValueError('illegal control/order')
        except ValueError:
            self.fault = True
            raise


class Credits:
    """Eight initial slots; cumulative modulo-32 consumption acknowledgments.

    A fresh shared epoch initializes both ends. Credit words use the reverse
    bus, outside the payload FIFO. No timeout can invent a credit.
    """
    def __init__(self):
        self.available=8
        self.last=0

    def take(self):
        if self.available<=0:raise ValueError('no credit')
        self.available-=1

    def grant(self,count):
        if type(count) is not int or not 0<=count<32:raise ValueError('credit range')
        delta=(count-self.last)%32
        if delta>8-self.available:raise ValueError('stale/impossible credit')
        self.available+=delta
        self.last=count


class DirectSession:
    """Chip-owned finite transport, invalidated by STOP and configuration changes.

    Host parsing and credits remain external. This connects transport ownership;
    it does not establish physical capture or analog readiness.
    """
    def __init__(self, chip):
        from block_receiver_model import BlockFIFO
        from bit_event_stream import RawBurstPlayback
        self.chip = chip
        self.epoch = chip.epoch
        self.rx = BlockFIFO()
        self.tx = BlockFIFO()
        self.decoder = Decoder()
        self.playback = RawBurstPlayback(capacity_bits=128)
        self.consumed = 0
        self.closed = False

    def require_active(self):
        if (self.closed or self.chip.direct_session is not self
                or self.chip.epoch != self.epoch or self.chip.state != 'active'
                or self.chip.resources.get('engine') != 'wire'):
            raise ValueError('Stale or inactive direct transport')

    def advance(self, time):
        self.require_active()
        try:
            self.chip.advance(time)
        except ValueError:
            if self.chip.state == 'fault':self.chip.release_wired_output()
            raise
        self.require_active()

    def accept(self, cell):
        self.require_active()
        try:
            for record in self.decoder.feed(cell):
                if record[0] in ('data', 'event'):
                    self.playback.enqueue([record])
                elif record[0] == 'abort':
                    self.playback.queue.clear()
                    self.playback.bits = self.playback.boundaries = 0
                    self.playback.active = False
        except ValueError:
            self.chip.state = 'fault'
            self.chip.release_wired_output()
            self.playback.fault = True
            raise

    def tick(self):
        self.require_active()
        try:
            return self.playback.tick()
        except ValueError:
            self.chip.state = 'fault'
            self.chip.release_wired_output()
            raise

    def close(self):
        self.closed = True
        self.playback.fault = True
        self.playback.queue.clear()
        self.playback.bits = self.playback.boundaries = 0


class SampledBurstRecords:
    """Generic sampled-bit/quiet to records; no packet length or protocol syntax.

    Tick delays are explicit pipeline assumptions, not acquired clock timing.
    Holds only one partial byte. The consumer owns finite transport buffering.
    """
    def __init__(self, *, ui_ticks=5, quiet_samples=2):
        if type(ui_ticks) is not int or ui_ticks<=0:raise ValueError('Positive UI tick count required')
        if type(quiet_samples) is not int or not 1<=quiet_samples<=8:raise ValueError('Quiet qualification must be1..8samples')
        self.quiet_samples=quiet_samples;self.quiet_count=0
        self.ui=ui_ticks;self.active=False;self.closed=False
        self.partial=0;self.count=0;self.last_time=-1;self.last_ready=0

    def observe(self, time, bit):
        if type(time) is not int or time<=self.last_time or (bit is not None and (type(bit) is not int or bit not in (0,1))):
            raise ValueError('Increasing integer sample times and bit or quiet required')
        if self.closed and bit is not None:raise ValueError('Arm a new burst after END')
        self.last_time=time;out=[]
        def emit(delay,cell):
            self.last_ready=max(self.last_ready,time+delay*self.ui)
            out.append((self.last_ready,cell))
        if bit is None:
            if self.active:
                self.quiet_count+=1
                if self.quiet_count<self.quiet_samples:return out
                if self.count:
                    emit(8,word(0x10+self.count));emit(8,word(self.partial,True))
                emit(12,word(END))
                self.partial=0;self.count=0;self.active=False;self.closed=True
            return out
        if self.active and self.quiet_count:
            # Signal returned after an unqualified quiet sample: a bit is
            # missing. Never silently splice the remainder into a valid burst.
            emit(12,word(ABORT))
            self.partial=0;self.count=0;self.active=False;self.closed=True
            return out
        if not self.active:
            self.active=True;emit(16,word(START))
        self.partial|=bit<<self.count;self.count+=1
        if self.count==8:
            emit(9,word(self.partial,True));self.partial=0;self.count=0
        return out
