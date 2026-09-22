"""Stateful NRZ serializer and one-pole channel, prescribed mid-bit sampling."""
import math

class WiredChannel:
    def __init__(self, rate_bps, bandwidth_ratio=1,swing=1.,postcursor=0.):
        if not all(math.isfinite(v) for v in (rate_bps,bandwidth_ratio,swing,postcursor)) or rate_bps<=0 or bandwidth_ratio<=0 or swing<=0 or not 0<=postcursor<1:
            raise ValueError('Invalid wired channel/driver parameters')
        self.swing=swing;self.postcursor=postcursor;self.previous_symbol=0.;self.peak_drive=0.
        self.rate=rate_bps
        self.decay=math.exp(-2*math.pi*bandwidth_ratio)
        self.state=0.
        self.bits=self.errors=0
        self.minimum_margin=float('inf')
    def word(self, value):
        result=0
        for bit in range(10):
            symbol=1 if value & (1 << bit) else -1
            drive=self.swing*(symbol-self.postcursor*self.previous_symbol)/(1+self.postcursor)
            self.previous_symbol=symbol;self.peak_drive=max(self.peak_drive,abs(drive))
            sampled=drive+(self.state-drive)*math.sqrt(self.decay)
            self.state=drive+(self.state-drive)*self.decay
            result |= int(sampled>0) << bit
            margin=sampled*symbol
            self.minimum_margin=min(self.minimum_margin,margin)
            self.errors+=int(margin<=0)
            self.bits+=1
        return result
    def report(self):
        return dict(swing=self.swing,postcursor=self.postcursor,peak_drive=self.peak_drive,bits=self.bits,observed_bit_errors=self.errors,
                    minimum_signed_margin=self.minimum_margin,
                    clock='prescribed mid-bit phase; no CDR')

def controls():
    a=WiredChannel(1e9)
    assert a.word(1023)==1023
    assert abs(a.state-(1-math.exp(-20*math.pi)))<1e-14
    b=WiredChannel(1e9)
    assert b.word(0)==0 and abs(a.state+b.state)<1e-14
    slow=WiredChannel(1e9,.03)
    for _ in range(20):slow.word(0x155)
    assert slow.errors>0
